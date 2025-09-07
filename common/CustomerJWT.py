from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from django.utils import timezone


class CustomJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        token_iat = validated_token.get('iat')

        # Convert token issue time to datetime
        token_issue_date = timezone.datetime.fromtimestamp(token_iat, tz=timezone.utc)

        # Check if token was issued before password change
        if user.password_changed_at and token_issue_date < user.password_changed_at:
            raise InvalidToken('Token is invalid due to password change')

        return user
