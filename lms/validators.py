import re
from urllib.parse import urlparse

from rest_framework.serializers import ValidationError

# Ищем в тексте любые http/https-ссылки
URL_PATTERN = re.compile(r'https?://[^\s<>"\')\]]+', re.IGNORECASE)

# Разрешённые хосты. youtu.be — официальный короткий домен YouTube
ALLOWED_HOSTS = ('youtube.com', 'youtu.be')


def is_allowed(url: str) -> bool:
    """Ссылка ведёт на youtube.com (или его поддомен) либо на youtu.be."""
    host = (urlparse(url).hostname or '').lower()
    return any(host == allowed or host.endswith(f'.{allowed}') for allowed in ALLOWED_HOSTS)


class LinksValidator:
    """Запрещает ссылки на сторонние ресурсы.

    Проверяет одно поле сериализатора: вытаскивает из его значения все
    http/https-ссылки и пропускает только те, что ведут на youtube.com.

    Используется в Meta сериализатора:
        validators = [LinksValidator(field='video_url')]
    """

    def __init__(self, field: str):
        self.field = field

    def __call__(self, value):
        text = dict(value).get(self.field)
        if not text:
            # Поля нет в запросе (partial update) или оно пустое — проверять нечего
            return

        forbidden = [url for url in URL_PATTERN.findall(str(text)) if not is_allowed(url)]
        if forbidden:
            raise ValidationError({
                self.field: (
                    'В материалах можно размещать ссылки только на youtube.com. '
                    f'Запрещённые ссылки: {", ".join(forbidden)}'
                )
            })
