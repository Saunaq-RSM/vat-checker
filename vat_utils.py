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
    """Send SOAP request and return parsed result."""
    soap = build_soap(country, number)
    resp = requests.post(VIES_ENDPOINT, headers=HEADERS, data=soap, timeout = 10)
    resp.raise_for_status()
    return parse_response(resp.text)
