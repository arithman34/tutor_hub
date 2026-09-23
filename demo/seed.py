import argparse
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import delete, func, select

from app.auth import hash_password
from app.core.database import async_session, engine
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.payee import Payee
from app.models.payment import Payment
from app.models.session import Session
from app.models.student import Student
from app.models.user import PayoutType, User, UserRole
from app.services.ingestion import chunk_text, embed_texts

DEMO_PASSWORD = "demo-password"
WEEKS = 8


@dataclass
class DemoStudent:
    first_name: str
    last_name: str
    level: str
    subject: str
    hourly_rate: float
    payee: str
    tutor: str
    weekday: int
    hour: int  # UTC
    first_week: int = 0  # weeks after the start of the demo period


TUTORS = {
    "priya": dict(first_name="Priya", last_name="Shah", email="priya.shah@example.com",
                  payout_type=PayoutType.percentage, payout_percentage=50.0),
    "tom": dict(first_name="Tom", last_name="Hughes", email="tom.hughes@example.com",
                payout_type=PayoutType.hourly, payout_hourly_rate=15.0),
}

PAYEES = {
    "collins": dict(first_name="Sarah", last_name="Collins", email="sarah.collins@example.com",
                    phone_number="+447700900101", bank_reference_pattern="COLLINS"),
    "okafor": dict(first_name="David", last_name="Okafor", email="david.okafor@example.com",
                   phone_number="+447700900102", bank_reference_pattern="OKAFOR"),
    "wright": dict(first_name="Helen", last_name="Wright", email="helen.wright@example.com",
                   phone_number="+447700900103", bank_reference_pattern="WRIGHT"),
    "patel": dict(first_name="Mark", last_name="Patel", email="mark.patel@example.com",
                  phone_number="+447700900104", bank_reference_pattern="PATEL"),
}

STUDENTS = [
    DemoStudent("Emily", "Collins", "GCSE", "Maths", 35, "collins", "priya", weekday=0, hour=16),
    DemoStudent("Jack", "Collins", "A-Level", "Physics", 40, "collins", "priya", weekday=1, hour=17),
    DemoStudent("Amara", "Okafor", "A-Level", "Maths", 40, "okafor", "priya", weekday=2, hour=16),
    DemoStudent("Oliver", "Wright", "GCSE", "Physics", 35, "wright", "priya", weekday=3, hour=17),
    DemoStudent("Riya", "Patel", "GCSE", "Maths", 35, "patel", "tom", weekday=0, hour=18, first_week=2),
    DemoStudent("Ben", "Patel", "A-Level", "Chemistry", 40, "patel", "tom", weekday=2, hour=18, first_week=4),
]

TOPICS = {
    ("GCSE", "Maths"): ["Fractions and ratio", "Simultaneous equations", "Pythagoras' theorem",
                        "Trigonometry (SOH CAH TOA)", "Probability trees", "Circle theorems",
                        "Straight-line graphs", "Quadratic equations"],
    ("A-Level", "Maths"): ["Binomial expansion", "Differentiation from first principles", "Chain rule",
                           "Product and quotient rules", "Integration by substitution", "Trig identities",
                           "Exponentials and logarithms", "Stationary points"],
    ("GCSE", "Physics"): ["Speed and velocity", "Newton's laws", "Energy stores", "Specific heat capacity",
                          "Series and parallel circuits", "Waves", "Density", "Radioactive decay"],
    ("A-Level", "Physics"): ["SUVAT equations", "Projectile motion", "Momentum", "Work and power",
                             "Stress and strain", "Electric fields", "Circular motion", "Simple harmonic motion"],
    ("A-Level", "Chemistry"): ["Atomic structure", "Amount of substance", "Bonding", "Energetics",
                               "Kinetics", "Equilibria", "Organic nomenclature", "Redox"],
}

# The session shown in the README screenshot: Emily's most recent lesson.
FEATURED_SUMMARY = (
    "Emily and the tutor reviewed quadratic equations. Emily factorised simple quadratics confidently "
    "but struggled when the coefficient of x squared was greater than 1. They worked through completing "
    "the square with three examples, and Emily solved the last one on her own. The tutor set exercise 4B "
    "questions 1 to 10 for homework. Next lesson will cover the quadratic formula and the discriminant."
)
FEATURED_NOTES = dict(
    work_covered=(
        "Reviewed factorising quadratics, then moved on to quadratics where the coefficient of x squared is "
        "greater than 1. Introduced completing the square and worked through three examples together; Emily "
        "solved the third independently."
    ),
    student_actions="- Complete exercise 4B, questions 1 to 10\n- Write out the completing-the-square steps from memory",
    tutor_actions="- Prepare a quadratic formula worksheet\n- Pick two past-paper questions on the discriminant",
    next_lesson_focus="Derive and apply the quadratic formula, then use the discriminant to count roots.",
    topic_tags="quadratics, factorising, completing the square",
)

# Original revision notes written for the demo, one string per PDF page.
DOCUMENTS = [
    dict(
        title="Differentiation Rules - Revision Notes",
        document_type="notes", subject="Maths", level="A-Level", exam_board="OCR",
        source_url="differentiation-rules.pdf",
        pages=[
            "Differentiation measures the rate of change of a function. For a power of x, multiply by the "
            "power and reduce the power by one: the derivative of x^n is n x^(n-1). Constants differentiate "
            "to zero, and a constant multiple stays in front of the derivative. The derivative of e^x is e^x, "
            "the derivative of ln x is 1/x, the derivative of sin x is cos x and the derivative of cos x is "
            "-sin x.",
            "The product rule: if y = u v, then dy/dx = u dv/dx + v du/dx. Use it when two functions of x are "
            "multiplied together, for example x^2 sin x. The quotient rule: if y = u / v, then "
            "dy/dx = (v du/dx - u dv/dx) / v^2. A common mistake is reversing the order of the terms in the "
            "numerator, which flips the sign of the answer.",
            "The chain rule handles a function of a function: if y = f(g(x)), then dy/dx = f'(g(x)) g'(x). "
            "In practice, differentiate the outer function, keep the inside unchanged, then multiply by the "
            "derivative of the inside. For example, the derivative of (3x + 1)^5 is 15(3x + 1)^4. Stationary "
            "points occur where dy/dx = 0; use the second derivative to decide whether each one is a maximum "
            "or a minimum.",
        ],
    ),
    dict(
        title="Quadratics - Revision Notes",
        document_type="notes", subject="Maths", level="GCSE", exam_board="AQA",
        source_url="quadratics.pdf",
        pages=[
            "A quadratic has the form ax^2 + bx + c = 0. There are three ways to solve one: factorising, "
            "completing the square, and the quadratic formula. Try factorising first; if the numbers do not "
            "work out neatly, use the formula.",
            "Completing the square rewrites x^2 + bx + c as (x + b/2)^2 - (b/2)^2 + c. The turning point of "
            "the graph is then (-b/2, c - (b/2)^2). The quadratic formula is x = (-b plus or minus the square "
            "root of (b^2 - 4ac)) / 2a. The discriminant b^2 - 4ac tells you how many real roots there are: "
            "two if it is positive, one if it is zero, and none if it is negative.",
        ],
    ),
    dict(
        title="Forces and Motion - Revision Notes",
        document_type="notes", subject="Physics", level="GCSE", exam_board="AQA",
        source_url="forces-and-motion.pdf",
        pages=[
            "Newton's first law: an object stays at rest or moves at a constant velocity unless a resultant "
            "force acts on it. Newton's second law: resultant force = mass x acceleration (F = m a), with force "
            "in newtons, mass in kilograms and acceleration in metres per second squared. Newton's third law: "
            "when two objects interact, they exert equal and opposite forces on each other.",
            "Speed = distance / time. Velocity is speed in a given direction. Acceleration = change in velocity "
            "/ time taken. On a velocity-time graph, the gradient is the acceleration and the area under the "
            "line is the distance travelled. Stopping distance = thinking distance + braking distance.",
        ],
    ),
]


def _session_times(student: DemoStudent, now: datetime) -> list[datetime]:
    """Weekly lesson start times for a student, oldest first, all in the past."""
    this_monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    period_start = this_monday - timedelta(weeks=WEEKS - 1)
    starts = []
    for week in range(student.first_week, WEEKS):
        start = period_start + timedelta(weeks=week, days=student.weekday, hours=student.hour)
        if start + timedelta(hours=1) <= now:
            starts.append(start)
    return starts


def _notes(student: DemoStudent, topic: str) -> dict:
    return dict(
        work_covered=f"Worked through {topic.lower()} with a mix of worked examples and exam-style questions.",
        student_actions=f"- Finish the {topic.lower()} practice questions",
        tutor_actions="- Mark homework and pick two past-paper questions for next time",
        next_lesson_focus=f"Consolidate {topic.lower()} before moving on.",
        topic_tags=topic.lower(),
    )


async def _seed_documents(db) -> int:
    count = 0
    for spec in DOCUMENTS:
        raw_chunks = [c for number, text in enumerate(spec["pages"], start=1) for c in chunk_text(text, number)]
        embeddings = await embed_texts([c["content"] for c in raw_chunks])
        document = Document(**{k: v for k, v in spec.items() if k != "pages"})
        db.add(document)
        await db.flush()
        for index, (raw, embedding) in enumerate(zip(raw_chunks, embeddings)):
            db.add(Chunk(document_id=document.id, content=raw["content"], embedding=embedding,
                         page_number=raw["page_number"], chunk_index=index))
        count += 1
    return count


async def reset(db) -> None:
    """Delete everything a previous run created, leaving any other rows alone."""
    tutor_ids = select(User.id).where(User.email.in_([t["email"] for t in TUTORS.values()]))
    payee_ids = select(Payee.id).where(Payee.email.in_([p["email"] for p in PAYEES.values()]))
    document_ids = select(Document.id).where(Document.title.in_([d["title"] for d in DOCUMENTS]))

    await db.execute(delete(Chunk).where(Chunk.document_id.in_(document_ids)))
    await db.execute(delete(Document).where(Document.id.in_(document_ids)))
    await db.execute(delete(Payment).where(Payment.payee_id.in_(payee_ids)))
    await db.execute(delete(Session).where(Session.user_id.in_(tutor_ids)))
    await db.execute(delete(Student).where(Student.user_id.in_(tutor_ids)))
    await db.execute(delete(Payee).where(Payee.id.in_(payee_ids)))
    await db.execute(delete(User).where(User.id.in_(tutor_ids)))
    await db.commit()


async def seed(reset_first: bool) -> None:
    now = datetime.now(timezone.utc)

    async with async_session() as db:
        if reset_first:
            await reset(db)

        if await db.scalar(select(func.count()).select_from(Student)):
            raise SystemExit(
                "This database already has students. The demo seed only runs on an empty database; "
                "use --reset to replace data from a previous demo run."
            )

        admin = (await db.execute(
            select(User).where(User.role.in_([UserRole.admin, UserRole.admin_tutor])).limit(1)
        )).scalar_one_or_none()
        if admin is None:
            admin = User(email="admin@example.com", hashed_password=hash_password(DEMO_PASSWORD),
                         first_name="Alex", last_name="Morgan", role=UserRole.admin)
            db.add(admin)

        tutors = {key: User(**fields, hashed_password=hash_password(DEMO_PASSWORD), role=UserRole.tutor)
                  for key, fields in TUTORS.items()}
        payees = {key: Payee(**fields, user=admin) for key, fields in PAYEES.items()}
        db.add_all([*tutors.values(), *payees.values()])
        await db.flush()

        # Cost of each payee's sessions, grouped by fortnight, drives the payments below.
        fortnight_costs: dict[tuple[str, int], float] = {}
        period_start = now - timedelta(weeks=WEEKS)
        session_count = 0
        featured_session = None

        for spec in STUDENTS:
            student = Student(first_name=spec.first_name, last_name=spec.last_name, level=spec.level,
                              hourly_rate=spec.hourly_rate, user_id=tutors[spec.tutor].id,
                              payee_id=payees[spec.payee].id)
            db.add(student)
            await db.flush()

            starts = _session_times(spec, now)
            topics = TOPICS[(spec.level, spec.subject)]
            for i, start in enumerate(starts):
                is_latest = i == len(starts) - 1
                is_no_show = spec.first_name == "Oliver" and i == len(starts) - 3
                if spec.first_name == "Emily" and is_latest:
                    notes = dict(FEATURED_NOTES, zoom_summary_raw=FEATURED_SUMMARY)
                elif is_no_show:
                    notes = {}
                else:
                    notes = _notes(spec, topics[i % len(topics)])

                # The session lists only show sessions linked to a calendar
                # event, so each one gets a placeholder event ID.
                session = Session(user_id=student.user_id, student_id=student.id, session_date=start,
                                  session_start_time=start, session_end_time=start + timedelta(hours=1),
                                  is_no_show=is_no_show, calendar_event_id=f"demo-{student.id.hex[:8]}-{i}",
                                  **notes)
                db.add(session)
                session_count += 1
                if "zoom_summary_raw" in notes:
                    featured_session = session

                fortnight = (start - period_start).days // 14
                key = (spec.payee, fortnight)
                fortnight_costs[key] = fortnight_costs.get(key, 0) + spec.hourly_rate

        # Parents pay each fortnight a few days after it ends. The Wrights miss
        # their latest payment so the dashboard has an overdue balance to show.
        payments = []
        for (payee_key, fortnight), amount in sorted(fortnight_costs.items()):
            paid_on = period_start + timedelta(days=14 * (fortnight + 1) + 3)
            if paid_on <= now:
                payments.append((payee_key, paid_on, amount))
        wright_payments = [p for p in payments if p[0] == "wright"]
        if wright_payments:
            payments.remove(wright_payments[-1])

        for payee_key, paid_on, amount in payments:
            payee = payees[payee_key]
            db.add(Payment(user_id=admin.id, payee_id=payee.id, amount=Decimal(str(amount)), payment_date=paid_on,
                           payment_reference=f"{payee.bank_reference_pattern} TUITION"))
        payment_count = len(payments)

        await db.commit()

        try:
            document_count = await _seed_documents(db)
            await db.commit()
        except Exception as exc:
            await db.rollback()
            document_count = 0
            print(f"Skipped documents, the OpenAI embedding call failed: {exc}")

    print(f"Created 2 tutors, {len(PAYEES)} payees, {len(STUDENTS)} students, {session_count} sessions, "
          f"{payment_count} payments and {document_count} documents.")
    print(f"Tutor logins: {', '.join(t['email'] for t in TUTORS.values())} (password: {DEMO_PASSWORD})")
    if admin.email == "admin@example.com":
        print(f"Admin login: admin@example.com (password: {DEMO_PASSWORD})")
    if featured_session is not None:
        print(f"Emily's parsed session (log in as Priya): http://localhost:8000/sessions/{featured_session.id}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Fill a local database with fictional demo data.")
    parser.add_argument("--reset", action="store_true", help="delete data from a previous demo run first")
    args = parser.parse_args()
    try:
        await seed(reset_first=args.reset)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
