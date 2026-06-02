import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

from fastapi import HTTPException, status
from sqlmodel import Session, select

from models import ContractStatus, ContractType, PropertyListing, SRLContract

PROMESA_DE_VENTA_TEMPLATE = """# PROMESA DE VENTA DE INMUEBLE

**República Dominicana**  
**Fecha de ejecución:** {execution_date}  
**Referencia interna:** SRL-{remote_id}  
**Código de inmueble (RE/MAX):** {remote_id}

---

## I. PARTES CONTRATANTES

**PROMITENTE VENDEDOR(A):**  
Nombre: **{seller_name}**  
Documento de identidad / RNC: **{seller_id}**

**PROMITENTE COMPRADOR(A):**  
Nombre: **{buyer_name}**  
Documento de identidad / RNC: **{buyer_id}**

Las partes declaran tener capacidad legal suficiente para obligarse en los términos del presente instrumento, conforme a las leyes de la República Dominicana.

---

## II. OBJETO DEL CONTRATO

El VENDEDOR promete vender, y el COMPRADOR promete comprar, el siguiente inmueble:

| Campo | Detalle |
| :--- | :--- |
| **Descripción** | {property_title} |
| **Ubicación / Sector** | {property_sector} |
| **Precio de venta pactado** | {property_price} |
| **Referencia de listado** | #{remote_id} |

El inmueble se transmitirá libre de gravámenes, embargos y ocupantes no autorizados, salvo las excepciones expresamente declaradas por escrito por el VENDEDOR y aceptadas por el COMPRADOR.

---

## III. PRECIO Y ESTRUCTURA DE PAGO

1. **Precio total de venta:** {property_price} (valor expresado en dólares estadounidenses, salvo conversión expresa acordada por las partes).
2. **Arras confirmatorias / depósito inicial:** El COMPRADOR entregará al momento de la firma definitiva la suma equivalente al depósito de seriedad negocial acordado en el presente instrumento, aplicable al precio final.
3. **Saldo:** El remanente del precio será pagado al otorgamiento de la escritura definitiva de venta ante Notario Público competente.
4. **Forma de pago:** Transferencia bancaria certificada, cheque de gerencia, o instrumento financiero aceptado mutuamente por las partes.

---

## IV. PLAZOS Y CONDICIONES SUSPENSIVAS

1. Las partes se comprometen a suscribir la escritura pública de venta dentro del plazo máximo de **noventa (90) días calendario** contados a partir de la fecha del presente contrato, salvo prórroga escrita.
2. El COMPRADOR podrá realizar inspecciones técnicas, revisión documental de título, y verificación registral del inmueble dentro de los primeros **quince (15) días** posteriores a la firma de esta promesa.
3. Si se descubriere gravamen no revelado, defecto de titularidad, o impedimento registral insalvable, el COMPRADOR podrá resolver el contrato y solicitar la devolución de sumas entregadas, sin penalidad, dentro de los plazos legales aplicables.

---

## V. OBLIGACIONES DEL VENDEDOR

1. Entregar certificaciones de título, impuestos municipales, IPI, y documentos de identidad requeridos para la formalización.
2. Mantener el inmueble en el estado observado durante la visita comercial, salvo deterioro por caso fortuito.
3. Abstenerse de negociar, prometer, o enajenar el inmueble a terceros durante la vigencia de esta promesa.
4. Cooperar con la formalización notarial y el proceso de cierre registral (Registro de Títulos).

---

## VI. OBLIGACIONES DEL COMPRADOR

1. Proveer documentación personal y financiera razonablemente requerida para el cierre.
2. Proceder con la apertura de escrow o cuenta de depósito en garantía, si las partes así lo acuerdan.
3. Asumir los gastos de registro, honorarios notariales, y retenciones legalmente atribuibles al adquirente, salvo pacto distinto.
4. Cumplir con los plazos de pago establecidos, bajo pena de incurrir en mora conforme a la legislación dominicana.

---

## VII. INCUMPLIMIENTO Y PENALIDADES

1. El incumplimiento injustificado de cualquiera de las partes facultará a la parte cumplida a exigir el cumplimiento específico o la resolución del contrato con indemnización de daños y perjuicios.
2. Si el COMPRADOR incumpliere sin causa justificada, las arras podrán ser retenidas por el VENDEDOR conforme a la naturaleza jurídica otorgada a dichas sumas.
3. Si el VENDEDOR incumpliere sin causa justificada, deberá restituir las sumas recibidas en doble concepto de penalidad convencional, sin perjuicio de otras acciones disponibles.

---

## VIII. GASTOS, IMPUESTOS Y COMISIONES

Salvo acuerdo escrito en contrario, cada parte asumirá sus honorarios profesionales. Los impuestos de transferencia, gastos registrales, y certificaciones se distribuirán conforme a la práctica notarial dominicana y lo pactado en el cierre.

---

## IX. LEY APLICABLE Y JURISDICCIÓN

Este contrato se regirá por las leyes de la **República Dominicana**. Para cualquier controversia, las partes se someten a los tribunales competentes del Distrito Nacional, renunciando a cualquier otro fuero que pudiera corresponderles.

---

## X. DISPOSICIONES FINALES

1. Toda modificación deberá constar por escrito y firmada por ambas partes.
2. La nulidad parcial de alguna cláusula no afectará la validez de las demás.
3. Este documento constituye una **PROMESA DE VENTA** en estado de borrador (**DRAFT**) generado por el sistema All Blue Legal Assembly Engine, sujeto a revisión por asesor legal licenciado antes de su firma definitiva.

---

**FIRMAS (Pendientes de formalización notarial)**

| Promitente Vendedor(a) | Promitente Comprador(a) |
| :--- | :--- |
| _________________________ | _________________________ |
| {seller_name} | {buyer_name} |
| Cédula/RNC: {seller_id} | Cédula/RNC: {buyer_id} |
"""

CONTRATO_DE_ALQUILER_TEMPLATE = """# CONTRATO DE ALQUILER DE INMUEBLE

**República Dominicana**  
**Fecha de ejecución:** {execution_date}  
**Referencia interna:** SRL-{remote_id}  
**Código de inmueble (RE/MAX):** {remote_id}

---

## I. PARTES CONTRATANTES

**ARRENDADOR(A):**  
Nombre: **{seller_name}**  
Documento de identidad / RNC: **{seller_id}**

**ARRENDATARIO(A):**  
Nombre: **{buyer_name}**  
Documento de identidad / RNC: **{buyer_id}**

Las partes convienen celebrar el presente contrato de arrendamiento conforme a la Ley No. 252-2020 sobre Alquiler de Inmuebles Urbanos y demás normas aplicables en la República Dominicana.

---

## II. OBJETO Y DESTINO DEL INMUEBLE

El ARRENDADOR cede en arrendamiento al ARRENDATARIO el inmueble descrito a continuación:

| Campo | Detalle |
| :--- | :--- |
| **Descripción** | {property_title} |
| **Ubicación / Sector** | {property_sector} |
| **Canon mensual pactado** | {property_price} |
| **Referencia de listado** | #{remote_id} |

**Uso permitido:** Residencial / habitacional, salvo autorización escrita para uso distinto.  
Queda prohibido subarrendar, ceder, o destinar el inmueble a actividades ilícitas, ruidosas, o contrarias al reglamento de copropiedad.

---

## III. PLAZO DEL ARRENDAMIENTO

1. **Duración:** Doce (12) meses consecutivos, contados a partir de la fecha de entrega de llaves.
2. **Renovación:** Podrá renovarse mediante acuerdo escrito suscrito con al menos treinta (30) días de anticipación al vencimiento.
3. **Entrega:** El ARRENDADOR entregará el inmueble en buen estado de conservación, con inventario firmado por ambas partes.

---

## IV. CANON, DEPÓSITO Y FORMA DE PAGO

1. **Canon mensual:** {property_price}, pagadero por adelantado dentro de los primeros cinco (5) días calendario de cada mes.
2. **Depósito de garantía:** Equivalente a un (1) mes de canon, depositado al inicio del contrato para responder por daños, rentas vencidas, y servicios pendientes al término del arrendamiento.
3. **Mora:** El retraso en el pago generará recargos y acciones de desahucio conforme a la ley, previo requerimiento fehaciente.
4. **Método de pago:** Transferencia bancaria o instrumento acordado, con comprobante exigible.

---

## V. GASTOS, MANTENIMIENTO Y SERVICIOS

1. **Servicios públicos (luz, agua, gas, internet, cable):** Correrán por cuenta del ARRENDATARIO, salvo pacto distinto.
2. **Cuota de mantenimiento / condominio:** Será pagada por el ARRENDATARIO si el inmueble se encuentra en régimen de propiedad horizontal, salvo que el ARRENDADOR asuma expresamente dicho gasto por escrito.
3. **Reparaciones menores:** Corresponden al ARRENDATARIO (cerraduras, bombillas, desagües menores por uso ordinario).
4. **Reparaciones mayores estructurales:** Corresponden al ARRENDADOR (techo, estructura, instalaciones principales no deterioradas por mal uso).

---

## VI. OBLIGACIONES DEL ARRENDADOR

1. Garantizar el uso pacífico del inmueble durante la vigencia del contrato.
2. Atender reclamaciones de reparaciones mayores en plazo razonable.
3. Mantener vigente el seguro del inmueble si así se hubiere pactado.
4. Respetar los períodos de preaviso legal para visitas de inspección, salvo emergencias.

---

## VII. OBLIGACIONES DEL ARRENDATARIO

1. Pagar puntualmente el canon y los servicios a su cargo.
2. Conservar el inmueble en buen estado, permitiendo inspecciones programadas.
3. No realizar mejoras estructurales sin autorización escrita del ARRENDADOR.
4. Restituir el inmueble al término del contrato en condiciones similares a la entrega, salvo deterioro normal.

---

## VIII. TERMINACIÓN ANTICIPADA Y DESAHUCIO

1. Cualquiera de las partes podrá terminar anticipadamente conforme a los plazos y causales establecidos en la Ley 252-2020 y sus reglamentos.
2. El incumplimiento grave facultará a la parte afectada a iniciar acciones de desahucio y cobro de rentas adeudadas.
3. La devolución del depósito de garantía se efectuará dentro de los treinta (30) días posteriores a la entrega, previa deducción justificada por daños o deudas.

---

## IX. SEGURO Y RESPONSABILIDAD

Las partes podrán exigir póliza de seguro contra incendio y responsabilidad civil, cuyo costo será asumido conforme al acuerdo de cierre. El ARRENDATARIO responderá por daños causados por negligencia, visitas, o incumplimiento de normas de convivencia.

---

## X. LEY APLICABLE Y JURISDICCIÓN

Este contrato se regirá por las leyes de la **República Dominicana**, incluyendo la Ley 252-2020. Las controversias serán sometidas a los tribunales competentes del Distrito Nacional.

---

## XI. DISPOSICIONES FINALES

1. Toda enmienda requerirá documento escrito firmado por ambas partes.
2. Este instrumento se genera en estado **DRAFT** por el sistema All Blue Legal Assembly Engine y debe ser revisado por abogado licenciado antes de su firma definitiva.
3. La firma de este borrador no sustituye el registro ni formalización exigida para su oposibilidad plena ante terceros, cuando corresponda.

---

**FIRMAS (Pendientes de formalización definitiva)**

| Arrendador(a) | Arrendatario(a) |
| :--- | :--- |
| _________________________ | _________________________ |
| {seller_name} | {buyer_name} |
| Cédula/RNC: {seller_id} | Cédula/RNC: {buyer_id} |
"""


def parse_business_type(raw_description: str, title: str) -> str:
    segments = [segment.strip().lower() for segment in raw_description.split("|")]
    for segment in segments:
        if "alquiler" in segment:
            return "alquiler"
        if "venta" in segment:
            return "venta"
    if "alquiler" in title.lower():
        return "alquiler"
    return "venta"


def format_property_price(property_listing: PropertyListing) -> str:
    currency_match = re.search(r"currency=([A-Z]{3})", property_listing.raw_description, re.IGNORECASE)
    currency = currency_match.group(1).upper() if currency_match else "USD"

    if currency == "DOP" and property_listing.price_dop:
        formatted = f"RD${property_listing.price_dop:,.2f}"
        usd_note = f" (equivalente referencial: US${property_listing.price_usd:,.2f})"
        return formatted + usd_note

    return f"US${property_listing.price_usd:,.2f}"


SPANISH_MONTHS = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


def build_template_context(
    property_listing: PropertyListing,
    buyer_name: str,
    buyer_id: str,
    seller_name: str,
    seller_id: str,
) -> Dict[str, str]:
    now = datetime.now(timezone.utc)
    execution_date = (
        f"{now.day} de {SPANISH_MONTHS[now.month - 1]} de {now.year}"
    )
    return {
        "property_title": property_listing.title,
        "property_price": format_property_price(property_listing),
        "property_sector": f"{property_listing.sector}, {property_listing.province}",
        "remote_id": property_listing.remote_id,
        "buyer_name": buyer_name,
        "seller_name": seller_name,
        "buyer_id": buyer_id,
        "seller_id": seller_id,
        "execution_date": execution_date,
    }


def compile_contract_markdown(business_type: str, context: Dict[str, str]) -> str:
    if business_type == "alquiler":
        template = CONTRATO_DE_ALQUILER_TEMPLATE
    else:
        template = PROMESA_DE_VENTA_TEMPLATE
    return template.format(**context)


def resolve_contract_type(business_type: str) -> ContractType:
    if business_type == "alquiler":
        return ContractType.RENTAL
    return ContractType.PURCHASE_RESERVATION


def calculate_earnest_deposit(total_value_usd: float, business_type: str) -> float:
    if business_type == "alquiler":
        return round(total_value_usd, 2)
    return round(total_value_usd * 0.10, 2)


def generate_contract_number(remote_id: str) -> str:
    timestamp = int(time.time())
    return f"SRL-{remote_id}-{timestamp}"


def resolve_property(session: Session, property_id: str) -> PropertyListing:
    property_listing = session.exec(
        select(PropertyListing).where(PropertyListing.id == property_id)
    ).first()

    if property_listing is None:
        property_listing = session.exec(
            select(PropertyListing).where(PropertyListing.remote_id == property_id)
        ).first()

    if property_listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Property '{property_id}' was not found in real_estate.properties.",
        )

    return property_listing


def contract_to_response(contract: SRLContract, property_listing: PropertyListing, business_type: str) -> Dict[str, Any]:
    return {
        "id": contract.id,
        "contract_number": contract.contract_number,
        "property_id": contract.property_id,
        "property_remote_id": contract.property_remote_id,
        "property_title": property_listing.title,
        "business_type": business_type,
        "contract_type": contract.contract_type,
        "status": contract.status,
        "client_name": contract.client_name,
        "client_rnc_or_cedula": contract.client_rnc_or_cedula,
        "buyer_name": contract.buyer_name,
        "buyer_id": contract.buyer_id,
        "seller_name": contract.seller_name,
        "seller_id": contract.seller_id,
        "total_value_usd": contract.total_value_usd,
        "earnest_deposit_usd": contract.earnest_deposit_usd,
        "execution_date": contract.execution_date,
        "document_body": contract.document_body,
        "last_modified": contract.last_modified,
        "server_version": contract.server_version,
    }


def initialize_contract(
    session: Session,
    property_id: str,
    buyer_name: str,
    buyer_id: str,
    seller_name: str,
    seller_id: str,
) -> Tuple[SRLContract, PropertyListing, str]:
    property_listing = resolve_property(session, property_id)
    business_type = parse_business_type(property_listing.raw_description, property_listing.title)

    context = build_template_context(
        property_listing=property_listing,
        buyer_name=buyer_name,
        buyer_id=buyer_id,
        seller_name=seller_name,
        seller_id=seller_id,
    )
    document_body = compile_contract_markdown(business_type, context)

    total_value_usd = property_listing.price_usd
    earnest_deposit_usd = calculate_earnest_deposit(total_value_usd, business_type)
    contract_type = resolve_contract_type(business_type)

    contract = SRLContract(
        contract_number=generate_contract_number(property_listing.remote_id),
        property_id=property_listing.id,
        property_remote_id=property_listing.remote_id,
        client_name=buyer_name,
        client_rnc_or_cedula=buyer_id,
        buyer_name=buyer_name,
        buyer_id=buyer_id,
        seller_name=seller_name,
        seller_id=seller_id,
        contract_type=contract_type,
        total_value_usd=total_value_usd,
        earnest_deposit_usd=earnest_deposit_usd,
        execution_date=datetime.now(timezone.utc),
        status=ContractStatus.DRAFT,
        document_body=document_body,
    )

    session.add(contract)
    session.commit()
    session.refresh(contract)

    return contract, property_listing, business_type


def get_contract(session: Session, contract_id: str) -> Tuple[SRLContract, PropertyListing, str]:
    contract = session.exec(select(SRLContract).where(SRLContract.id == contract_id)).first()

    if contract is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract '{contract_id}' was not found.",
        )

    property_listing = session.exec(
        select(PropertyListing).where(PropertyListing.id == contract.property_id)
    ).first()

    if property_listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Linked property '{contract.property_id}' was not found for contract '{contract_id}'.",
        )

    business_type = parse_business_type(property_listing.raw_description, property_listing.title)
    return contract, property_listing, business_type