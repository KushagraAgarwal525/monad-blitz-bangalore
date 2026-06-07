from openai import OpenAI

from app.config import settings


class FireworksClient:
    def __init__(self):
        self.client = OpenAI(
            api_key=settings.fireworks_api_key or "dummy",
            base_url=settings.fireworks_base_url,
        )
        self.chat_model = settings.fireworks_chat_model
        self.embedding_model = settings.fireworks_embedding_model
        self.embedding_dimensions = settings.fireworks_embedding_dimensions

    def embed_text(self, text: str) -> list[float]:
        if not settings.fireworks_api_key:
            import hashlib
            h = hashlib.sha256(text.encode()).digest()
            return [((h[i % 32] / 255.0) - 0.5) for i in range(self.embedding_dimensions)]
        resp = self.client.embeddings.create(
            model=self.embedding_model,
            input=text,
            dimensions=self.embedding_dimensions,
        )
        return resp.data[0].embedding

    def chat_completion(self, messages: list[dict], json_mode: bool = False) -> str:
        if not settings.fireworks_api_key:
            return "Demo mode: configure FIREWORKS_API_KEY for live responses."
        kwargs = {"model": self.chat_model, "messages": messages}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = self.client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""
