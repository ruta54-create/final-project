"""Development email backend: saves each email as an .eml file in backend/sent_emails/.

Double-click a .eml file to open it in Outlook / Windows Mail / Thunderbird and see the email
exactly as the recipient would. Used automatically when no SMTP server is configured.
"""

from django.core.mail.backends.filebased import EmailBackend


class EmlFileBackend(EmailBackend):
    def _get_filename(self):
        if self._fname is None:
            name = super()._get_filename()
            self._fname = name[:-4] + ".eml" if name.endswith(".log") else name
        return self._fname
