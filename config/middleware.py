from django.http import JsonResponse

HEALTH_PATH = "/api/health/"


class HealthCheckMiddleware:
    """
    Answers the platform's health probe before anything else runs.
    Django rejects requests whose Host header is not in ALLOWED_HOSTS, and redirects
    plain-HTTP requests to HTTPS. A load balancer's health probe often sends neither
    the public host name nor HTTPS, so without this the platform would mark a
    perfectly healthy service as failed. Only this one path is affected, and it
    returns nothing sensitive.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == HEALTH_PATH:
            return JsonResponse({"status": "ok"})
        return self.get_response(request)
