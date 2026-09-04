from django.db import migrations


def add_general_architecture_service(apps, schema_editor):
    Service = apps.get_model("services", "Service")
    name = "General Architecture & Technical Scoping"
    description = (
        "Not sure which technical service fits your project? Work directly with a lead software architect "
        "to define MVP requirements, evaluate technology trade-offs, estimate timelines, and choose the optimal tech stack."
    )
    Service.objects.get_or_create(
        name=name,
        defaults={"description": description, "is_active": True}
    )


def remove_general_architecture_service(apps, schema_editor):
    Service = apps.get_model("services", "Service")
    Service.objects.filter(name="General Architecture & Technical Scoping").delete()


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0003_alter_engineerexpertise_options_and_more'),
    ]

    operations = [
        migrations.RunPython(add_general_architecture_service, remove_general_architecture_service),
    ]
