from django.db import migrations


def remove_general_architecture_service(apps, schema_editor):
    Service = apps.get_model("services", "Service")
    Appointment = apps.get_model("appointments", "Appointment")

    gen_service = Service.objects.filter(name__icontains="General Architecture").first()
    if gen_service:
        alt_service = Service.objects.filter(name__icontains="Cloud Migration").first()
        if not alt_service:
            alt_service = Service.objects.exclude(id=gen_service.id).first()

        if alt_service:
            Appointment.objects.filter(service=gen_service).update(service=alt_service)
        gen_service.delete()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0004_seed_general_architecture_service'),
        ('appointments', '0002_appointment_cancellation_reason'),
    ]

    operations = [
        migrations.RunPython(remove_general_architecture_service, noop),
    ]
