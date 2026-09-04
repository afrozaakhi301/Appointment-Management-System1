from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from accounts.decorators import engineer_required
from accounts.models import EngineerProfile, User
from dashboard.utils import log_activity
from scheduling.models import EngineerAvailability
from .forms import EngineerExpertiseForm
from .models import EngineerExpertise, Expertise, Service


def home_view(request):
    services = Service.objects.filter(is_active=True)[:6]
    engineers = User.objects.filter(role=User.Role.ENGINEER, is_active=True).select_related("engineer_profile").prefetch_related("engineer_expertises__expertise")[:4]
    expertises = Expertise.objects.all()[:10]
    return render(
        request,
        "services/home.html",
        {
            "services": services,
            "engineers": engineers,
            "expertises": expertises,
        }
    )


def about_contact_view(request):
    return render(request, "services/about_contact.html")


def service_list_view(request):
    services = Service.objects.filter(is_active=True)
    return render(
        request,
        "services/service_list.html",
        {"services": services}
    )


def engineer_list_view(request):
    query = request.GET.get("q", "").strip()
    expertise_id = request.GET.get("expertise", "").strip()
    tag = request.GET.get("tag", "").strip().lower()
    experience = request.GET.get("experience", "").strip().lower()
    proficiency = request.GET.get("proficiency", "").strip()
    sort_by = request.GET.get("sort", "exp_desc").strip()

    from django.db.models import Avg, Count
    engineers = User.objects.filter(
        role=User.Role.ENGINEER, 
        is_active=True
    ).select_related("engineer_profile").prefetch_related("engineer_expertises__expertise").annotate(
        avg_rating=Avg("engineer_appointments__feedback__rating"),
        review_count=Count("engineer_appointments__feedback", distinct=True)
    )

    # 1. Search Query
    if query:
        engineers = engineers.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(username__icontains=query) |
            Q(engineer_profile__designation__icontains=query) |
            Q(engineer_profile__bio__icontains=query) |
            Q(engineer_expertises__expertise__name__icontains=query)
        )

    # 2. Specific Expertise Filter
    if expertise_id:
        engineers = engineers.filter(engineer_expertises__expertise_id=expertise_id)

    # 3. Quick Tag Filter
    if tag:
        if tag == "cloud":
            engineers = engineers.filter(
                Q(engineer_expertises__expertise__name__icontains="AWS") |
                Q(engineer_expertises__expertise__name__icontains="Cloud") |
                Q(engineer_profile__designation__icontains="Cloud")
            )
        elif tag == "python":
            engineers = engineers.filter(
                Q(engineer_expertises__expertise__name__icontains="Python") |
                Q(engineer_expertises__expertise__name__icontains="Django") |
                Q(engineer_profile__designation__icontains="Python") |
                Q(engineer_profile__designation__icontains="Full-Stack")
            )
        elif tag == "database":
            engineers = engineers.filter(
                Q(engineer_expertises__expertise__name__icontains="Database") |
                Q(engineer_expertises__expertise__name__icontains="PostgreSQL") |
                Q(engineer_expertises__expertise__name__icontains="Redis") |
                Q(engineer_profile__designation__icontains="Database")
            )
        elif tag == "devops":
            engineers = engineers.filter(
                Q(engineer_expertises__expertise__name__icontains="DevOps") |
                Q(engineer_expertises__expertise__name__icontains="Docker") |
                Q(engineer_expertises__expertise__name__icontains="Kubernetes") |
                Q(engineer_expertises__expertise__name__icontains="Terraform") |
                Q(engineer_profile__designation__icontains="DevOps")
            )
        elif tag == "microservices":
            engineers = engineers.filter(
                Q(engineer_expertises__expertise__name__icontains="Microservices") |
                Q(engineer_expertises__expertise__name__icontains="gRPC") |
                Q(engineer_profile__designation__icontains="Microservices")
            )
        elif tag == "security":
            engineers = engineers.filter(
                Q(engineer_expertises__expertise__name__icontains="Security") |
                Q(engineer_expertises__expertise__name__icontains="OWASP") |
                Q(engineer_profile__designation__icontains="Security") |
                Q(engineer_profile__designation__icontains="QA")
            )

    # 4. Experience Filter
    if experience == "junior":
        engineers = engineers.filter(engineer_profile__years_of_experience__lte=3)
    elif experience == "mid":
        engineers = engineers.filter(engineer_profile__years_of_experience__gte=4, engineer_profile__years_of_experience__lte=6)
    elif experience == "senior":
        engineers = engineers.filter(engineer_profile__years_of_experience__gte=7, engineer_profile__years_of_experience__lte=9)
    elif experience == "lead":
        engineers = engineers.filter(engineer_profile__years_of_experience__gte=10)

    # 5. Proficiency Level Filter
    if proficiency:
        engineers = engineers.filter(engineer_expertises__proficiency_level=proficiency)

    engineers = engineers.distinct()

    # 6. Sorting
    if sort_by == "exp_asc":
        engineers = engineers.order_by("engineer_profile__years_of_experience", "first_name")
    elif sort_by == "name_asc":
        engineers = engineers.order_by("first_name", "last_name")
    elif sort_by == "name_desc":
        engineers = engineers.order_by("-first_name", "-last_name")
    elif sort_by == "rating_desc":
        engineers = engineers.order_by("-avg_rating", "-engineer_profile__years_of_experience")
    else:  # exp_desc default
        engineers = engineers.order_by("-engineer_profile__years_of_experience", "first_name")

    expertises = Expertise.objects.all()
    proficiency_choices = EngineerExpertise.ProficiencyLevel.choices

    # Calculate active filter count
    active_filters_count = sum([
        1 if query else 0,
        1 if expertise_id else 0,
        1 if tag else 0,
        1 if experience else 0,
        1 if proficiency else 0,
        1 if sort_by != "exp_desc" else 0
    ])

    return render(
        request,
        "services/engineer_list.html",
        {
            "engineers": engineers,
            "expertises": expertises,
            "proficiency_choices": proficiency_choices,
            "query": query,
            "selected_expertise": expertise_id,
            "selected_tag": tag,
            "selected_experience": experience,
            "selected_proficiency": proficiency,
            "selected_sort": sort_by,
            "active_filters_count": active_filters_count,
            "total_count": engineers.count(),
        }
    )


def engineer_detail_view(request, engineer_id):
    engineer = get_object_or_404(User, id=engineer_id, role=User.Role.ENGINEER, is_active=True)
    profile, _ = EngineerProfile.objects.get_or_create(user=engineer)
    expertises = engineer.engineer_expertises.select_related("expertise")
    availabilities = EngineerAvailability.objects.filter(engineer=engineer).order_by("day_of_week", "start_time")

    return render(
        request,
        "services/engineer_detail.html",
        {
            "engineer": engineer,
            "profile": profile,
            "expertises": expertises,
            "availabilities": availabilities,
        }
    )


@engineer_required
def engineer_manage_expertise(request):
    engineer = request.user
    my_expertises = EngineerExpertise.objects.filter(engineer=engineer).select_related("expertise")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "delete":
            item_id = request.POST.get("item_id")
            item = get_object_or_404(EngineerExpertise, id=item_id, engineer=engineer)
            item_name = item.expertise.name
            item.delete()
            log_activity(engineer, f"Removed expertise: {item_name}")
            messages.success(request, f"Removed expertise '{item_name}'.")
            return redirect("services:manage_my_expertise")
        else:
            form = EngineerExpertiseForm(request.POST)
            if form.is_valid():
                expertise_obj = form.cleaned_data["expertise"]
                if EngineerExpertise.objects.filter(engineer=engineer, expertise=expertise_obj).exists():
                    messages.warning(request, f"You have already added '{expertise_obj.name}'.")
                else:
                    item = form.save(commit=False)
                    item.engineer = engineer
                    item.save()
                    log_activity(engineer, f"Added expertise: {expertise_obj.name} ({item.proficiency_level})")
                    messages.success(request, f"Added '{expertise_obj.name}' ({item.proficiency_level}) to your profile.")
                    return redirect("services:manage_my_expertise")
    else:
        form = EngineerExpertiseForm()

    return render(
        request,
        "services/manage_my_expertise.html",
        {
            "form": form,
            "my_expertises": my_expertises,
        }
    )
