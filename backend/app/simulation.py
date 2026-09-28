"""Template roleplay adapter: local, deterministic, no outgoing telephony/network."""
from dataclasses import dataclass


@dataclass
class SimulatedReply:
    text: str
    connected: bool
    contact_id: str | None = None


def simulate_contact(snapshot: dict, phone: str, message: str | None = None) -> dict:
    contact=next((c for c in snapshot.get('contacts',[]) if c['phone']==phone),None)
    if contact is None:
        return {'text':'Учебный номер не найден. Проверьте справочник контактов.','connected':False,'contact_id':None}
    text=contact['greeting'] if message is None else contact['reply']
    return {'text':text,'connected':True,'contact_id':contact['id']}
