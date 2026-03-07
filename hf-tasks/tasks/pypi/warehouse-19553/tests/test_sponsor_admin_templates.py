# SPDX-License-Identifier: Apache-2.0

from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader


def _render_admin_template(template_name, **context):
    env = Environment(
        loader=ChoiceLoader(
            [
                DictLoader({"admin/base.html": "{% block content %}{% endblock %}"}),
                FileSystemLoader("warehouse/admin/templates"),
            ]
        ),
        autoescape=True,
    )
    template = env.get_template(template_name)

    class DummyRequest:
        def route_path(self, *args, **kwargs):
            return "/"

        def current_route_path(self):
            return "/"

        def has_permission(self, *args, **kwargs):
            return True

        session = type("Session", (), {"get_csrf_token": lambda self: "token"})()

    permissions = type("Permissions", (), {"AdminSponsorsWrite": object()})()

    class DummyField:
        def __init__(self):
            self.errors = []

        def __call__(self, **kwargs):
            return "<input>"

    class DummyForm:
        def __init__(self):
            self.form_errors = []
            self.name = DummyField()
            self.is_active = DummyField()
            self.service = DummyField()
            self.link_url = DummyField()
            self.color_logo = DummyField()
            self.white_logo = DummyField()
            self.activity_markdown = DummyField()
            self.footer = DummyField()
            self.psf_sponsor = DummyField()
            self.infra_sponsor = DummyField()
            self.one_time = DummyField()
            self.sidebar = DummyField()

    form = DummyForm()
    return template.render(
        request=DummyRequest(), form=form, Permissions=permissions, **context
    )


def test_sponsor_edit_shows_logo_urls_and_pythondotorg_metadata():
    class DummySponsor:
        name = "Example Sponsor"
        color_logo_url = "https://example.com/logo.png"
        white_logo_url = "https://example.com/white-logo.png"
        origin = "remote"
        level_name = "Platinum"
        level_order = 42
        is_active = False

    rendered = _render_admin_template(
        "admin/sponsors/edit.html", sponsor=DummySponsor()
    )

    assert "sponsor-color-logo-url" in rendered
    assert "sponsor-white-logo-url" in rendered
    assert "sponsor-origin" in rendered
    assert "sponsor-level-name" in rendered
    assert "sponsor-level-order" in rendered
    assert "Platinum" in rendered
    assert "42" in rendered


def test_sponsor_edit_does_not_render_plaintext_logo_inputs_when_creating():
    rendered = _render_admin_template("admin/sponsors/edit.html", sponsor=None)

    assert "sponsor-color-logo-url" not in rendered
    assert "sponsor-white-logo-url" not in rendered
    assert "sponsor-origin" not in rendered
    assert "sponsor-level-name" not in rendered
    assert "sponsor-level-order" not in rendered
