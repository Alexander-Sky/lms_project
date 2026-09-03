from rest_framework.pagination import PageNumberPagination


class CoursePaginator(PageNumberPagination):
    """Пагинация списка курсов.

    Курс отдаётся вместе со всеми уроками, поэтому страница маленькая.
    Размер можно переопределить в запросе: ?page_size=5
    """

    page_size = 3
    page_size_query_param = 'page_size'
    max_page_size = 10


class LessonPaginator(PageNumberPagination):
    """Пагинация списка уроков."""

    page_size = 5
    page_size_query_param = 'page_size'
    max_page_size = 20
