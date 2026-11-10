"""Give translation codes to command messages saved before the dashboard was multilingual,
so old rows also appear in French / Kinyarwanda instead of English."""

import re

from django.db import migrations

REJECTED = re.compile(r"^Rejected: (organic|inorganic) depth ([\d.]+) cm")


def backfill(apps, schema_editor):
    Command = apps.get_model("bins", "Command")
    Command.objects.filter(message="Device did not answer in time", message_code="").update(message_code="expired")
    for cmd in Command.objects.filter(message__startswith="Rejected:", message_code=""):
        m = REJECTED.match(cmd.message)
        if m:
            cmd.message_code = "depth_too_small"
            cmd.message_params = {"compartment": m.group(1), "value": float(m.group(2))}
            cmd.save(update_fields=["message_code", "message_params"])


class Migration(migrations.Migration):
    dependencies = [("bins", "0002_i18n_codes")]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
