"""Page Object de l'écran de connexion `/login`.

Écran autonome (formulaire email/mot de passe, bascule connexion/inscription,
message d'erreur, redirection vers le tableau de bord après succès).

Règles (playwright.dev/docs/best-practices) :
  • un Page Object décrit des INTERACTIONS et des LECTURES, il n'assertionne pas ;
  • les locators sont centralisés ici : une refonte de l'UI ne casse qu'un fichier ;
  • ordre de préférence : role > label > placeholder > texte > testid > CSS.
    Jamais de XPath ;
  • aucune attente arbitraire (sleep) : uniquement des attentes sur condition
    observable (web-first `expect` côté spec).
"""

from __future__ import annotations

from playwright.sync_api import Locator, Page


class LoginPage:
    """Page `/login` — formulaire d'authentification (connexion et inscription)."""

    PATH = "/login"
    READY_TIMEOUT_MS = 10_000

    def __init__(self, page: Page, base_url: str = "") -> None:
        self.page = page
        self.base_url = base_url.rstrip("/")

        self.auth_box: Locator = page.locator(".auth-box")
        self.form: Locator = page.locator("#auth-form")
        self.email_input: Locator = page.get_by_placeholder("Email")
        self.password_input: Locator = page.get_by_placeholder("Mot de passe")
        self.submit_button: Locator = page.locator("#auth-btn")
        self.subtitle: Locator = page.locator("#subtitle")
        self.error_message: Locator = page.locator("#error-msg")
        self.toggle_link: Locator = page.locator("#toggle-link")
        self.toggle_text: Locator = page.locator("#toggle-text")
        self.loader: Locator = page.locator("#loader")

    # --- navigation -------------------------------------------------------
    def open(self) -> "LoginPage":
        """Ouvre la page de connexion et attend que le formulaire soit rendu."""
        self.page.goto(f"{self.base_url}{self.PATH}", wait_until="domcontentloaded")
        self.form.wait_for(state="visible", timeout=self.READY_TIMEOUT_MS)
        return self

    # --- interactions -----------------------------------------------------
    def toggle_mode(self) -> "LoginPage":
        """Bascule entre connexion et inscription."""
        self.toggle_link.click()
        return self

    def fill(self, email: str, password: str) -> "LoginPage":
        self.email_input.fill(email)
        self.password_input.fill(password)
        return self

    def submit(self) -> "LoginPage":
        self.submit_button.click()
        return self

    def sign_in(self, email: str, password: str) -> "LoginPage":
        return self.fill(email, password).submit()

    # --- lectures ---------------------------------------------------------
    def title(self) -> str:
        return self.page.title()

    def url(self) -> str:
        return self.page.url

    def error_text(self) -> str:
        return self.error_message.inner_text()

    def submit_label(self) -> str:
        return self.submit_button.inner_text()

    def subtitle_text(self) -> str:
        return self.subtitle.inner_text()

    def toggle_link_text(self) -> str:
        return self.toggle_link.inner_text()

    def email_is_valid(self) -> bool:
        """Validité HTML5 du champ email (required, type=email)."""
        return bool(self.email_input.evaluate("el => el.checkValidity()"))

    def password_is_valid(self) -> bool:
        """Validité HTML5 du champ mot de passe (required, minlength=6)."""
        return bool(self.password_input.evaluate("el => el.checkValidity()"))

    def password_type(self) -> str:
        """`password` attendu : la saisie ne doit jamais être lisible en clair."""
        return self.password_input.get_attribute("type") or ""
