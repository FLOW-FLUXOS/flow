from rest_framework.pagination import PageNumberPagination


class Paginacao(PageNumberPagination):
    """20 por página; o cliente pode pedir até 100 com ?page_size=."""
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
