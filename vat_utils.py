
import time
import requests
from xml.etree import ElementTree as ET

VIES_ENDPOINT = 'https://ec.europa.eu/taxation_customs/vies/services/checkVatService'
HEADERS = {'Content-Type': 'text/xml; charset=UTF-8'}

def build_soap(country: str, number: str) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<env:Envelope
 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
 xmlns:tns1="urn:ec.europa.eu:taxud:vies:services:checkVat"
 xmlns:env="http://schemas.xmlsoap.org/soap/envelope/"
 xmlns:ins0="urn:ec.europa.eu:taxud:vies:services:checkVat:types">
  <env:Body>
    <ins0:checkVat>
      <ins0:countryCode>{country}</ins0:countryCode>
      <ins0:vatNumber>{number}</ins0:vatNumber>
      <ins0:requesterCountryCode>NL</ins0:requesterCountryCode>
      <ins0:requesterVatNumber>NL009444452B01</ins0:requesterVatNumber>
    </ins0:checkVat>
  </env:Body>
</env:Envelope>'''

def parse_response(xml_text: str) -> dict:
    doc = ET.fromstring(xml_text)
    ns = {
        'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
        'vies': 'urn:ec.europa.eu:taxud:vies:services:checkVat:types'
    }
    # Check for a fault
    fault = doc.findtext('.//faultcode')
    if fault:
        if fault == 'env:Server':
          fault = 'Server Not Responding, try later'
        return {'valid': False, 'status': fault, 'details': ''}
    # True/False flag
    valid = doc.findtext('.//vies:valid', namespaces=ns) == 'true'
    # Grab the exact traderName/traderAddress
    name = doc.findtext('.//vies:name', namespaces=ns) or ''
    addr = doc.findtext('.//vies:address', namespaces=ns) or ''

    # Clean up whitespace
    addr = ' '.join(addr.split())
    # **Filter out the literal placeholders** if they slip through
    if name.strip().lower() == 'name':
        name = ''
    if addr.strip().lower() == 'address':
        addr = ''
    details = ' – '.join(filter(None, [name, addr]))
    return {
        'valid': valid,
        'status': 'Valid' if valid else 'Invalid',
        'details': details or '(name unavailable)',
        'name': name or '(name unavailable)',
        'address': addr or '(address unavailable)'
    }

def check_vat(country: str, number: str) -> dict:
    """Send SOAP request, handle timeouts, and retry server errors."""
    MAX_ITERATIONS = 6
    for attempt in range(1, MAX_ITERATIONS + 1):
        try:
            soap = build_soap(country, number)
            # Fixed timeout = 10 seconds
            resp = requests.post(VIES_ENDPOINT, headers=HEADERS, data=soap, timeout=120) #timeout=10
            resp.raise_for_status()
            result = parse_response(resp.text)

            # If server says "try later", wait and retry
            if result['status'] == 'Server Not Responding, try later' and attempt < MAX_ITERATIONS:
                wait_time = 2 ** (attempt - 1)  # exponential backoff: 1s, 2s, 4s, ...
                print(f"Attempt {attempt}: Server busy, retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue

            # If successful or invalid VAT, return the result
            return result

        except requests.Timeout:
            print(f"Attempt {attempt}: Timeout after 10 seconds.")
            if attempt == MAX_ITERATIONS:
                return {
                    'valid': False,
                    'status': 'Timeout after 10 seconds',
                    'details': '',
                    'name': '(timeout)',
                    'address': '(timeout)'
                }
            # Wait before retrying
            time.sleep(2 ** (attempt - 1))

        except requests.RequestException as e:
            # Any other request-related error
            return {
                'valid': False,
                'status': f'HTTP error: {e}',
                'details': '',
                'name': '(error)',
                'address': '(error)'
            }

    # If all attempts fail
    return {
        'valid': False,
        'status': 'Server Not Responding after retries',
        'details': '',
        'name': '(error)',
        'address': '(error)'
    }
