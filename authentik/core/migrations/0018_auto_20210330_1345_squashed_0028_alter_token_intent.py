# Generated by Django 3.2.8 on 2021-10-10 16:12

import uuid
from os import environ

import django.db.models.deletion
from django.apps.registry import Apps
from django.conf import settings
from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.models import Count

import authentik.core.models
import authentik.lib.models


def migrate_sessions(apps: Apps, schema_editor: BaseDatabaseSchemaEditor):
    db_alias = schema_editor.connection.alias
    from django.contrib.sessions.backends.cache import KEY_PREFIX
    from django.core.cache import cache

    session_keys = cache.keys(KEY_PREFIX + "*")
    cache.delete_many(session_keys)


def fix_duplicates(apps: Apps, schema_editor: BaseDatabaseSchemaEditor):
    db_alias = schema_editor.connection.alias
    Token = apps.get_model("authentik_core", "token")
    identifiers = (
        Token.objects.using(db_alias)
        .values("identifier")
        .annotate(identifier_count=Count("identifier"))
        .filter(identifier_count__gt=1)
    )
    for ident in identifiers:
        Token.objects.using(db_alias).filter(identifier=ident["identifier"]).delete()


def create_default_user_token(apps: Apps, schema_editor: BaseDatabaseSchemaEditor):
    # We have to use a direct import here, otherwise we get an object manager error
    from authentik.core.models import Token, TokenIntents, User

    db_alias = schema_editor.connection.alias

    akadmin = User.objects.using(db_alias).filter(username="akadmin")
    if not akadmin.exists():
        return
    if "AK_ADMIN_TOKEN" not in environ:
        return
    Token.objects.using(db_alias).create(
        identifier="authentik-boostrap-token",
        user=akadmin.first(),
        intent=TokenIntents.INTENT_API,
        expiring=False,
        key=environ["AK_ADMIN_TOKEN"],
    )


class Migration(migrations.Migration):

    replaces = [
        ("authentik_core", "0018_auto_20210330_1345"),
        ("authentik_core", "0019_source_managed"),
        ("authentik_core", "0020_source_user_matching_mode"),
        ("authentik_core", "0021_alter_application_slug"),
        ("authentik_core", "0022_authenticatedsession"),
        ("authentik_core", "0023_alter_application_meta_launch_url"),
        ("authentik_core", "0024_alter_token_identifier"),
        ("authentik_core", "0025_alter_application_meta_icon"),
        ("authentik_core", "0026_alter_application_meta_icon"),
        ("authentik_core", "0027_bootstrap_token"),
        ("authentik_core", "0028_alter_token_intent"),
    ]

    dependencies = [
        ("authentik_core", "0017_managed"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="token",
            options={
                "permissions": (("view_token_key", "View token's key"),),
                "verbose_name": "Token",
                "verbose_name_plural": "Tokens",
            },
        ),
        migrations.AddField(
            model_name="source",
            name="managed",
            field=models.TextField(
                default=None,
                help_text="Objects which are managed by authentik. These objects are created and updated automatically. This is flag only indicates that an object can be overwritten by migrations. You can still modify the objects via the API, but expect changes to be overwritten in a later update.",
                null=True,
                unique=True,
                verbose_name="Managed by authentik",
            ),
        ),
        migrations.AddField(
            model_name="source",
            name="user_matching_mode",
            field=models.TextField(
                choices=[
                    ("identifier", "Use the source-specific identifier"),
                    (
                        "email_link",
                        "Link to a user with identical email address. Can have security implications when a source doesn't validate email addresses.",
                    ),
                    (
                        "email_deny",
                        "Use the user's email address, but deny enrollment when the email address already exists.",
                    ),
                    (
                        "username_link",
                        "Link to a user with identical username. Can have security implications when a username is used with another source.",
                    ),
                    (
                        "username_deny",
                        "Use the user's username, but deny enrollment when the username already exists.",
                    ),
                ],
                default="identifier",
                help_text="How the source determines if an existing user should be authenticated or a new user enrolled.",
            ),
        ),
        migrations.AlterField(
            model_name="application",
            name="slug",
            field=models.SlugField(
                help_text="Internal application name, used in URLs.", unique=True
            ),
        ),
        migrations.CreateModel(
            name="AuthenticatedSession",
            fields=[
                (
                    "expires",
                    models.DateTimeField(default=authentik.core.models.default_token_duration),
                ),
                ("expiring", models.BooleanField(default=True)),
                ("uuid", models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ("session_key", models.CharField(max_length=40)),
                ("last_ip", models.TextField()),
                ("last_user_agent", models.TextField(blank=True)),
                ("last_used", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.RunPython(
            code=migrate_sessions,
        ),
        migrations.AlterField(
            model_name="application",
            name="meta_launch_url",
            field=models.TextField(
                blank=True, default="", validators=[authentik.lib.models.DomainlessURLValidator()]
            ),
        ),
        migrations.RunPython(
            code=fix_duplicates,
        ),
        migrations.AlterField(
            model_name="token",
            name="identifier",
            field=models.SlugField(max_length=255, unique=True),
        ),
        migrations.AlterField(
            model_name="application",
            name="meta_icon",
            field=models.FileField(default=None, null=True, upload_to="application-icons/"),
        ),
        migrations.AlterField(
            model_name="application",
            name="meta_icon",
            field=models.FileField(
                default=None, max_length=500, null=True, upload_to="application-icons/"
            ),
        ),
        migrations.AlterModelOptions(
            name="authenticatedsession",
            options={
                "verbose_name": "Authenticated Session",
                "verbose_name_plural": "Authenticated Sessions",
            },
        ),
        migrations.RunPython(
            code=create_default_user_token,
        ),
        migrations.AlterField(
            model_name="token",
            name="intent",
            field=models.TextField(
                choices=[
                    ("verification", "Intent Verification"),
                    ("api", "Intent Api"),
                    ("recovery", "Intent Recovery"),
                    ("app_password", "Intent App Password"),
                ],
                default="verification",
            ),
        ),
    ]
