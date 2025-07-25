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
    <ins0:checkVatApprox>
      <ins0:countryCode>{country}</ins0:countryCode>
      <ins0:vatNumber>{number}</ins0:vatNumber>
      <ins0:requesterCountryCode></ins0:requesterCountryCode>
      <ins0:requesterVatNumber></ins0:requesterVatNumber>
    </ins0:checkVatApprox>
  </env:Body>
</env:Envelope>'''

def parse_response(xml_text: str) -> dict:
    doc = ET.fromstring(xml_text)
    # namespaces cleanup
    ns = {'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
          'vies': 'urn:ec.europa.eu:taxud:vies:services:checkVat:types'}
    fault = doc.find('.//faultcode')
    if fault is not None:
        return {'valid': False, 'status': fault.text, 'details': ''}
    valid = doc.findtext('.//vies:valid', namespaces=ns) == 'true'
    name = doc.findtext('.//vies:name', namespaces=ns) or ''
    addr = doc.findtext('.//vies:address', namespaces=ns) or ''
    details = ' – '.join(filter(None, [name.strip(), ' '.join(addr.split())]))
    return {
      'valid': valid,
      'status': 'Valid' if valid else 'Invalid',
      'details': details or '(name unavailable)'
    }

def check_vat(country: str, number: str) -> dict:
    """Send SOAP request and return parsed result."""
    soap = build_soap(country, number)
    resp = requests.post(VIES_ENDPOINT, headers=HEADERS, data=soap)
    resp.raise_for_status()
    return parse_response(resp.text)
