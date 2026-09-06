from datetime import date, datetime, time, timedelta
from django.core.management.base import BaseCommand
from accounts.models import ClientProfile, EngineerProfile, User
from appointments.models import Appointment, AppointmentDocument
from dashboard.models import ActivityLog
from dashboard.utils import log_activity
from feedback.models import Feedback
from notifications.models import Notification
from notifications.utils import create_notification
from scheduling.models import EngineerAvailability, EngineerLeave
from services.models import EngineerExpertise, Expertise, Service


class Command(BaseCommand):
    help = "Seed database with realistic initial data for viva demonstration."

    def handle(self, *args, **options):
        self.stdout.write("Starting database seeding...")

        # 1. Admin User
        admin_user, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "first_name": "System",
                "last_name": "Administrator",
                "email": "admin@tns-software.com",
                "role": User.Role.ADMIN,
                "is_staff": True,
                "is_superuser": True,
                "phone_number": "+1-555-0100",
            }
        )
        admin_user.set_password("admin123")
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.role = User.Role.ADMIN
        admin_user.save()
        if created:
            log_activity(admin_user, "System Admin account initialized")

        # 2. Services
        services_data = [
            ("General Architecture & Technical Scoping", "Not sure which technical service fits your project? Work directly with a lead software architect to define MVP requirements, evaluate technology trade-offs, estimate timelines, and choose the optimal tech stack."),
            ("Cloud Migration & AWS/GCP Architecture", "End-to-end guidance on transitioning on-premises monoliths to scalable, resilient multi-cloud architectures with container orchestration."),
            ("Backend Performance & Database Optimization", "In-depth profiling, query plan optimization, indexing strategies, and database connection pooling for high-throughput applications."),
            ("DevOps CI/CD & Infrastructure as Code", "Modernization of delivery pipelines using GitHub Actions, GitLab CI, Terraform, Kubernetes Helm charts, and automated testing."),
            ("Microservices & API Strategy", "Domain-Driven Design (DDD), RESTful API standards, gRPC integration, message queues (Kafka, RabbitMQ), and distributed tracing."),
            ("Full-Stack Django & Python Code Review", "Comprehensive architectural and security inspection of Django codebases, clean architecture patterns, and asynchronous processing."),
            ("Mobile App Architecture & Cross-Platform Strategy", "End-to-end architecture guidance for iOS and Android apps, cross-platform selection (Flutter vs React Native), offline sync, and store publishing."),
            ("Cybersecurity Audit & Application Hardening", "Comprehensive security inspection of web platforms, OWASP Top 10 vulnerability mitigation, auth & session protection, and data privacy hardening."),
        ]
        service_objs = []
        for name, desc in services_data:
            svc, _ = Service.objects.get_or_create(name=name, defaults={"description": desc, "is_active": True})
            # Ensure description is updated if already created
            svc.description = desc
            svc.is_active = True
            svc.save()
            service_objs.append(svc)

        # 3. Expertise tags
        expertises_data = [
            "Python / Django",
            "Kubernetes & Docker",
            "PostgreSQL & Query Optimization",
            "AWS Solutions Architecture",
            "Microservices & gRPC",
            "DevOps & Terraform",
            "Redis & Distributed Caching",
            "System Security & OWASP",
            "Mobile App Development (Flutter & React Native)",
            "Cybersecurity & Penetration Testing",
        ]
        exp_objs = {}
        for name in expertises_data:
            exp, _ = Expertise.objects.get_or_create(name=name)
            exp_objs[name] = exp

        # 4. Software Engineers
        engineers_data = [
            {
                "username": "akter_hossain",
                "first_name": "Akter",
                "last_name": "Hossain",
                "email": "akter.hossain@tns-software.com",
                "phone": "+880 1711-000101",
                "designation": "Principal Cloud & Distributed Systems Architect",
                "experience": 10,
                "bio": "Specializes in high-scale cloud infrastructure, Kubernetes microservices orchestration, and multi-region AWS/GCP architecture for enterprise banking & telecom.",
                "skills": [
                    ("AWS Solutions Architecture", EngineerExpertise.ProficiencyLevel.LEAD),
                    ("Kubernetes & Docker", EngineerExpertise.ProficiencyLevel.EXPERT),
                    ("Microservices & gRPC", EngineerExpertise.ProficiencyLevel.EXPERT),
                ]
            },
            {
                "username": "angkon_debnath",
                "first_name": "Angkon",
                "last_name": "Debnath",
                "email": "angkon.debnath@tns-software.com",
                "phone": "+880 1812-000202",
                "designation": "Senior Full-Stack & Mobile Systems Engineer",
                "experience": 6,
                "bio": "Experienced full-stack & mobile engineer specialized in Flutter/React Native cross-platform apps, Django architectures, asynchronous task queues (Celery/Redis), and scalable REST/GraphQL API design.",
                "skills": [
                    ("Python / Django", EngineerExpertise.ProficiencyLevel.LEAD),
                    ("Mobile App Development (Flutter & React Native)", EngineerExpertise.ProficiencyLevel.LEAD),
                    ("Redis & Distributed Caching", EngineerExpertise.ProficiencyLevel.EXPERT),
                    ("System Security & OWASP", EngineerExpertise.ProficiencyLevel.INTERMEDIATE),
                ]
            },
            {
                "username": "khadiza_akter",
                "first_name": "Khadiza",
                "last_name": "Bint Akter",
                "email": "khadiza.akter@tns-software.com",
                "phone": "+880 1913-000303",
                "designation": "Lead Database & Backend Performance Engineer",
                "experience": 8,
                "bio": "Expert database architect and backend specialist focused on PostgreSQL query tuning, complex indexing strategies, sharding, and latency reduction.",
                "skills": [
                    ("PostgreSQL & Query Optimization", EngineerExpertise.ProficiencyLevel.LEAD),
                    ("Python / Django", EngineerExpertise.ProficiencyLevel.EXPERT),
                    ("Redis & Distributed Caching", EngineerExpertise.ProficiencyLevel.EXPERT),
                ]
            },
            {
                "username": "aizah_ayat",
                "first_name": "Aizah",
                "last_name": "Ayat",
                "email": "aizah.ayat@tns-software.com",
                "phone": "+880 1614-000404",
                "designation": "Staff DevOps & Cybersecurity Engineer",
                "experience": 7,
                "bio": "Focuses on automated GitOps pipelines, Terraform infrastructure-as-code, zero-trust security postures, application vulnerability hardening, and enterprise CI/CD modernization.",
                "skills": [
                    ("DevOps & Terraform", EngineerExpertise.ProficiencyLevel.LEAD),
                    ("Cybersecurity & Penetration Testing", EngineerExpertise.ProficiencyLevel.LEAD),
                    ("Kubernetes & Docker", EngineerExpertise.ProficiencyLevel.EXPERT),
                    ("System Security & OWASP", EngineerExpertise.ProficiencyLevel.LEAD),
                ]
            },
            {
                "username": "rashed_rana",
                "first_name": "Rashed",
                "last_name": "Rana",
                "email": "rashed.rana@tns-software.com",
                "phone": "+880 1715-000505",
                "designation": "Senior Microservices & Distributed Messaging Architect",
                "experience": 9,
                "bio": "Expert in event-driven architectures, Apache Kafka / RabbitMQ streaming, gRPC RPC contracts, and resilient domain-driven microservice decoupling.",
                "skills": [
                    ("Microservices & gRPC", EngineerExpertise.ProficiencyLevel.LEAD),
                    ("System Security & OWASP", EngineerExpertise.ProficiencyLevel.EXPERT),
                    ("Kubernetes & Docker", EngineerExpertise.ProficiencyLevel.EXPERT),
                ]
            },
            {
                "username": "shamsun_lata",
                "first_name": "Shamsun",
                "last_name": "Lata",
                "email": "shamsun.lata@tns-software.com",
                "phone": "+880 1816-000606",
                "designation": "Lead Cybersecurity Auditor & Application Security Specialist",
                "experience": 6,
                "bio": "Specializes in automated testing suites, application security audits (OWASP Top 10), penetration testing, code review governance, and vulnerability management.",
                "skills": [
                    ("Cybersecurity & Penetration Testing", EngineerExpertise.ProficiencyLevel.LEAD),
                    ("System Security & OWASP", EngineerExpertise.ProficiencyLevel.LEAD),
                    ("Python / Django", EngineerExpertise.ProficiencyLevel.EXPERT),
                    ("DevOps & Terraform", EngineerExpertise.ProficiencyLevel.INTERMEDIATE),
                ]
            },
            {
                "username": "mahin_khan",
                "first_name": "Mahin",
                "last_name": "Khan",
                "email": "mahin.khan@tns-software.com",
                "phone": "+880 1917-000707",
                "designation": "Senior Backend & Mobile Cloud Systems Engineer",
                "experience": 5,
                "bio": "Passionate backend & mobile architect specializing in Flutter cross-platform integration, cloud-native microservice development, database scaling, API gateway optimization, and serverless compute.",
                "skills": [
                    ("Mobile App Development (Flutter & React Native)", EngineerExpertise.ProficiencyLevel.EXPERT),
                    ("AWS Solutions Architecture", EngineerExpertise.ProficiencyLevel.EXPERT),
                    ("Python / Django", EngineerExpertise.ProficiencyLevel.EXPERT),
                    ("PostgreSQL & Query Optimization", EngineerExpertise.ProficiencyLevel.INTERMEDIATE),
                ]
            },
            {
                "username": "suyeb_ali",
                "first_name": "Suyeb",
                "last_name": "Ali",
                "email": "suyeb.ali@tns-software.com",
                "phone": "+880 1718-000808",
                "designation": "Principal Cloud Architect",
                "experience": 9,
                "bio": "Specializes in large-scale distributed systems, multi-cloud migrations (AWS/GCP), and Kubernetes orchestration.",
                "skills": [
                    ("AWS Solutions Architecture", EngineerExpertise.ProficiencyLevel.LEAD),
                    ("Kubernetes & Docker", EngineerExpertise.ProficiencyLevel.EXPERT),
                    ("Microservices & gRPC", EngineerExpertise.ProficiencyLevel.EXPERT),
                ]
            },
            {
                "username": "nadia_hossain",
                "first_name": "Nadia",
                "last_name": "Hossain",
                "email": "nadia.hossain@tns-software.com",
                "phone": "+880 1819-000909",
                "designation": "Staff Database & Backend Engineer",
                "experience": 7,
                "bio": "Expert in high-concurrency database architectures, PostgreSQL tuning, indexing optimization, Redis caching layers, and Python asynchronous services.",
                "skills": [
                    ("Python / Django", EngineerExpertise.ProficiencyLevel.LEAD),
                    ("PostgreSQL & Query Optimization", EngineerExpertise.ProficiencyLevel.EXPERT),
                    ("Redis & Distributed Caching", EngineerExpertise.ProficiencyLevel.EXPERT),
                ]
            },
            {
                "username": "wasim_kamal",
                "first_name": "Wasim",
                "last_name": "Kamal",
                "email": "wasim.kamal@tns-software.com",
                "phone": "+880 1920-001010",
                "designation": "Lead DevOps & Platform Security Engineer",
                "experience": 6,
                "bio": "Passionate about GitOps, automated infrastructure provisioning with Terraform, zero-downtime blue/green deployments, and security compliance.",
                "skills": [
                    ("DevOps & Terraform", EngineerExpertise.ProficiencyLevel.LEAD),
                    ("Cybersecurity & Penetration Testing", EngineerExpertise.ProficiencyLevel.EXPERT),
                    ("Kubernetes & Docker", EngineerExpertise.ProficiencyLevel.EXPERT),
                    ("System Security & OWASP", EngineerExpertise.ProficiencyLevel.INTERMEDIATE),
                ]
            }
        ]

        eng_objs = []
        for eng_data in engineers_data:
            eng_user, created = User.objects.get_or_create(
                username=eng_data["username"],
                defaults={
                    "first_name": eng_data["first_name"],
                    "last_name": eng_data["last_name"],
                    "email": eng_data["email"],
                    "phone_number": eng_data["phone"],
                    "role": User.Role.ENGINEER,
                }
            )
            if created:
                eng_user.set_password("Engineer123!")
                eng_user.save()

            profile, _ = EngineerProfile.objects.get_or_create(user=eng_user)
            profile.designation = eng_data["designation"]
            profile.years_of_experience = eng_data["experience"]
            profile.bio = eng_data["bio"]
            profile.save()

            # Assign skills
            for skill_name, prof_level in eng_data["skills"]:
                exp_obj = exp_objs.get(skill_name)
                if exp_obj:
                    ee, _ = EngineerExpertise.objects.get_or_create(
                        engineer=eng_user,
                        expertise=exp_obj,
                        defaults={
                            "proficiency_level": prof_level,
                            "status": EngineerExpertise.VerificationStatus.APPROVED
                        }
                    )
                    if ee.status != EngineerExpertise.VerificationStatus.APPROVED:
                        ee.status = EngineerExpertise.VerificationStatus.APPROVED
                        ee.save()

            # Assign weekly working hours (Monday through Friday 09:00 - 17:00)
            for day in range(0, 5):  # Mon-Fri
                EngineerAvailability.objects.get_or_create(
                    engineer=eng_user,
                    day_of_week=day,
                    start_time=time(9, 0),
                    end_time=time(17, 0)
                )

            eng_objs.append(eng_user)

        # 5. Clients
        clients_data = [
            {
                "username": "techcorp_client",
                "first_name": "Daniel",
                "last_name": "Brooks",
                "email": "dbrooks@techcorp.io",
                "phone": "+1-555-0301",
                "org": "TechCorp Logistics Inc.",
                "address": "450 Silicon Blvd, Suite 200, Austin, TX",
            },
            {
                "username": "fintech_client",
                "first_name": "Elena",
                "last_name": "Rostova",
                "email": "erostova@novapay.finance",
                "phone": "+1-555-0302",
                "org": "NovaPay Digital Banking",
                "address": "77 Wall Street, 14th Floor, New York, NY",
            }
        ]

        client_objs = []
        for c_data in clients_data:
            c_user, created = User.objects.get_or_create(
                username=c_data["username"],
                defaults={
                    "first_name": c_data["first_name"],
                    "last_name": c_data["last_name"],
                    "email": c_data["email"],
                    "phone_number": c_data["phone"],
                    "role": User.Role.CLIENT,
                }
            )
            if created:
                c_user.set_password("Client123!")
                c_user.save()

            c_prof, _ = ClientProfile.objects.get_or_create(user=c_user)
            c_prof.organization = c_data["org"]
            c_prof.address = c_data["address"]
            c_prof.save()

            client_objs.append(c_user)

        # 6. Sample Completed Consultation with Feedback
        # Next weekday calculation for future sample appointments
        today = date.today()
        # Find upcoming Monday
        days_ahead = (0 - today.weekday() + 7) % 7
        if days_ahead == 0:
            days_ahead = 7
        next_monday = today + timedelta(days=days_ahead)
        next_tuesday = next_monday + timedelta(days=1)

        past_date = today - timedelta(days=5)

        # Multi-timeframe completed appointments for daily/weekly/monthly tracking demonstration
        sample_completed_data = [
            {
                "title": "PostgreSQL Query Optimization & Index Audit",
                "client": client_objs[0],
                "engineer": eng_objs[1],  # Nadia
                "service": service_objs[1],  # Database
                "date": today,
                "start": time(10, 0),
                "end": time(11, 30),
                "desc": "Our logistics order tracking system was encountering 2-second query latencies on the primary orders table. Required deep indexing analysis.",
                "rating": 5,
                "review": "Nadia was phenomenal! She pinpointed the missing partial index in 15 minutes, reducing our latency from 2,100ms down to 18ms. Exceptional expertise."
            },
            {
                "title": "Kubernetes Microservices Mesh Ingress Setup",
                "client": client_objs[1],
                "engineer": eng_objs[0],  # Suyeb
                "service": service_objs[0],  # Cloud
                "date": today - timedelta(days=2),
                "start": time(14, 0),
                "end": time(15, 30),
                "desc": "Configuring Istio service mesh and traffic routing across microservices clusters.",
                "rating": 5,
                "review": "Suyeb demonstrated master-level knowledge of AWS EKS and Istio routing. Highly recommended."
            },
            {
                "title": "CI/CD Pipeline Security & Static Analysis Audit",
                "client": client_objs[0],
                "engineer": eng_objs[2],  # Wasim
                "service": service_objs[2],  # DevOps
                "date": today - timedelta(days=8),
                "start": time(11, 0),
                "end": time(12, 30),
                "desc": "Integrating SAST, secret scanning, and automated dependency vulnerability triage in GitHub Actions.",
                "rating": 4,
                "review": "Great session on pipeline hardening and automated SonarQube quality gates."
            },
            {
                "title": "Django ORM Query N+1 Bottleneck Refactor",
                "client": client_objs[1],
                "engineer": eng_objs[1],  # Nadia
                "service": service_objs[4],  # Python/Django
                "date": today - timedelta(days=18),
                "start": time(15, 0),
                "end": time(16, 30),
                "desc": "Resolving serious N+1 query explosion across multi-level nested foreign key serialization.",
                "rating": 5,
                "review": "Nadia utilized prefetch_related and selected subqueries to slice database hits from 450 queries down to 4 queries."
            },
            {
                "title": "Cloud Architecture High Availability Review",
                "client": client_objs[0],
                "engineer": eng_objs[0],  # Suyeb
                "service": service_objs[0],  # Cloud
                "date": today - timedelta(days=40),
                "start": time(10, 0),
                "end": time(11, 0),
                "desc": "Multi-region fallback and active-passive DNS failover strategies.",
                "rating": 5,
                "review": "Exceptional clarity on AWS Route 53 health routing and Aurora multi-master architecture."
            },
        ]

        for s_data in sample_completed_data:
            c_appt, _ = Appointment.objects.get_or_create(
                project_title=s_data["title"],
                defaults={
                    "client": s_data["client"],
                    "engineer": s_data["engineer"],
                    "service": s_data["service"],
                    "appointment_date": s_data["date"],
                    "start_time": s_data["start"],
                    "end_time": s_data["end"],
                    "project_description": s_data["desc"],
                    "requirements": "Standard architectural assessment and optimization.",
                    "status": Appointment.Status.COMPLETED,
                }
            )
            if not hasattr(c_appt, "feedback"):
                Feedback.objects.get_or_create(
                    appointment=c_appt,
                    defaults={
                        "rating": s_data["rating"],
                        "comments": s_data["review"]
                    }
                )

        # Upcoming Confirmed Appointment
        Appointment.objects.get_or_create(
            project_title="AWS Multi-Region Disaster Recovery Architecture",
            defaults={
                "client": client_objs[1],
                "engineer": eng_objs[0],  # Suyeb
                "service": service_objs[0],  # Cloud
                "appointment_date": next_monday,
                "start_time": time(14, 0),
                "end_time": time(15, 30),
                "project_description": "Designing automated failover between us-east-1 and us-west-2 for critical fintech ledger services.",
                "requirements": "Target RPO < 1 minute, RTO < 5 minutes. Need assessment of Aurora Global Database and Route 53 Application Recovery Controller.",
                "status": Appointment.Status.APPROVED,
            }
        )

        # Pending Request
        Appointment.objects.get_or_create(
            project_title="Kubernetes Helm Deployment Pipeline Migration",
            defaults={
                "client": client_objs[0],
                "engineer": eng_objs[2],  # Wasim
                "service": service_objs[2],  # DevOps
                "appointment_date": next_tuesday,
                "start_time": time(11, 0),
                "end_time": time(12, 0),
                "project_description": "We are migrating manual kubectl manifests to standard Helm charts and ArgoCD GitOps pipelines.",
                "requirements": "Review chart templating structure, secret management using Sealed Secrets, and rollback strategies.",
                "status": Appointment.Status.PENDING,
            }
        )

        self.stdout.write(self.style.SUCCESS("Database seeding completed successfully!"))
        self.stdout.write(self.style.SUCCESS("""
Test Credentials created:
---------------------------------------------
1. Admin Account:
   Username: admin
   Password: admin123

2. Bangladeshi Lead Software Engineers:
   - akter_hossain   (Password: Engineer123!) -> Principal Cloud Architect
   - angkon_debnath  (Password: Engineer123!) -> Senior Python / Django Engineer
   - khadiza_akter   (Password: Engineer123!) -> Lead Database & Backend Engineer
   - aizah_ayat      (Password: Engineer123!) -> Staff DevOps & Security Engineer
   - rashed_rana     (Password: Engineer123!) -> Senior Microservices Architect
   - shamsun_lata    (Password: Engineer123!) -> Lead QA & AppSec Specialist
   - mahin_khan      (Password: Engineer123!) -> Senior Cloud Native Engineer
   - suyeb_ali       (Password: Engineer123!) -> Principal Cloud Architect
   - nadia_hossain   (Password: Engineer123!) -> Staff Database & Backend Engineer
   - wasim_kamal     (Password: Engineer123!) -> Lead DevOps & Platform Security Engineer

3. Client Accounts:
   - techcorp_client (Password: Client123!)
   - fintech_client  (Password: Client123!)
---------------------------------------------
"""))
