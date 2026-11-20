"""LLM rolleri. Hepsi aynı ortak sohbet (transcript) üzerinden konuşur; birbirlerine GÜVENMEZ."""
import json
import re

TRUST_RULE = ("Diğer botların söylediklerine güvenme; her iddiayı kendin sorgula. "
              "Yanıtını SADECE tek bir JSON nesnesi olarak ver, başka metin yazma.")

HABERCI = ("Sen HABERCİ'sin. Bir kripto varlığında olağandışı hacim/fiyat hareketi tespit edildi. "
           "Görevin sebebini bulmak (haber, duyuru, X paylaşımı, listeleme, hack, makro olay). "
           "Her iddia için kaynak URL'si ZORUNLU. Kaynak bulamazsan sebebi 'bulunamadı' yaz, uydurma. "
           'JSON: {"reason": str, "sources": [url,...], "confidence": 0-1, "is_old_news": bool}. ' + TRUST_RULE)

STRATEJIST = ("Sen STRATEJİST'sin. Verilen veri ve haber ışığında LONG/SHORT planı çiz ya da plan yok de. "
              "Her plan için giriş, stop ve hedef ZORUNLU; stop girişe yakın, risk/ödül en az 1.5 olmalı. "
              "Emin değilsen plan verme. İtirazlara yanıt verirken planı sıkılaştırabilir ya da geri çekebilirsin. "
              'JSON: {"side": "LONG|SHORT|NONE", "entry": num, "stop": num, "target": num, "rationale": str}. ' + TRUST_RULE)

SUPHECI = ("Sen ŞÜPHECİ'sin. Her fikre itiraz etmek işin. Pump&dump, düşük likidite, geç kalmışlık, "
           "haberin eski/doğrulanamaz olması, stop'un avlanma riski, ücret/spread etkisi gibi noktaları sorgula. "
           "Gerçekten çürütülemez bir itiraz varsa blocking=true yap, yoksa false. "
           'JSON: {"objections": [str,...], "blocking": bool}. ' + TRUST_RULE)

MASA = ("Sen KARAR MASASI'sın. Tüm sohbeti oku ve TEK bir karar ver: LONG, SHORT, BEKLE veya GEÇ. "
        "Kurallar: kaynaksız haber -> BEKLE. Şüpheci'nin cevaplanmamış engelleyici itirazı -> GEÇ. "
        "Net bir avantaj yoksa BEKLE/GEÇ; çoğu karar işlem olmamalı. "
        'JSON: {"decision": "LONG|SHORT|BEKLE|GEÇ", "reason": str}. ' + TRUST_RULE)


def parse_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError(f"JSON bulunamadı: {text[:200]}")
    return json.loads(m.group(0))


class LLM:
    """Anthropic API sarmalayıcısı. Testlerde sahte bir sınıfla değiştirilir."""

    def __init__(self, model: str, api_key: str):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def ask(self, system: str, user: str, web_search: bool = False) -> str:
        kwargs = {}
        if web_search:
            kwargs["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}]
        msg = self.client.messages.create(model=self.model, max_tokens=1500, system=system,
                                          messages=[{"role": "user", "content": user}], **kwargs)
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
