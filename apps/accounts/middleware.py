"""Middleware to set/delete auth cookies from API responses.

Django Ninja doesn't provide direct access to the response object in
endpoint handlers. Instead, endpoints set request attributes that this
middleware reads and applies to the response.
"""


class AuthCookieMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Set auth cookie (from login endpoint)
        if hasattr(request, "_auth_cookie"):
            cookie = request._auth_cookie
            response.set_cookie(
                key=cookie["key"],
                value=cookie["value"],
                httponly=cookie.get("httponly", True),
                samesite=cookie.get("samesite", "Lax"),
                max_age=cookie.get("max_age", 28 * 24 * 3600),
            )

        # Delete auth cookie (from logout endpoint)
        if hasattr(request, "_delete_auth_cookie"):
            response.delete_cookie("auth_token")

        return response
