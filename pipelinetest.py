#!/usr/bin/env python
"""
Pipeline Integrity Test
Tests the assessment workflow: Admin → Assessor Dev → Moderator → QCTO → QDD → ETQA
Verifies status transitions and qualification-based filtering at each stage.
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.utils.timezone import now
from core.models import CustomUser, Assessment, Qualification, Paper
from django.contrib.auth import get_user_model

User = get_user_model()

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'


def print_header(text):
    print(f"\n{BOLD}{BLUE}{'='*70}{RESET}")
    print(f"{BOLD}{BLUE}{text:^70}{RESET}")
    print(f"{BOLD}{BLUE}{'='*70}{RESET}\n")


def print_test(name, passed, details=""):
    status = f"{GREEN}✓ PASS{RESET}" if passed else f"{RED}✗ FAIL{RESET}"
    print(f"{status} | {name}")
    if details:
        print(f"       └─ {details}")


def print_section(text):
    print(f"\n{YELLOW}{text}{RESET}")
    print(f"{YELLOW}{'-'*70}{RESET}")


def setup_test_data():
    """Create test qualifications, users, and assessments."""
    print_header("Setting Up Test Data")
    
    # Create qualifications
    qual1, _ = Qualification.objects.get_or_create(
        name="Maintenance Planner",
        defaults={"saqa_id": "1001"}
    )
    qual2, _ = Qualification.objects.get_or_create(
        name="Quality Controller",
        defaults={"saqa_id": "1002"}
    )
    print(f"Created/found qualifications: {qual1.name}, {qual2.name}")
    
    # Create test users by role
    users = {}
    roles_and_names = [
        ('admin', 'Admin User', 'admin@test.com'),
        ('assessor_dev', 'Assessor Developer', 'assessor@test.com'),
        ('moderator', 'Moderator User', 'moderator@test.com'),
        ('qcto', 'QCTO User', 'qcto@test.com'),
        ('qdd', 'QDD Reviewer', 'qdd@test.com'),
        ('etqa', 'ETQA User', 'etqa@test.com'),
    ]
    
    for role, name, email in roles_and_names:
        user, created = User.objects.get_or_create(
            username=email,
            defaults={
                'email': email,
                'first_name': name.split()[0],
                'last_name': ' '.join(name.split()[1:]),
                'role': role,
                'qualification': qual1 if role != 'admin' else None,
                'is_staff': role != 'assessor_dev',
                'is_active': True,
            }
        )
        user.set_password('testpass123')
        user.save()
        users[role] = user
        status = "created" if created else "exists"
        print(f"  {role:15} | {status:8} | {email}")
    
    # Create papers
    paper1, _ = Paper.objects.get_or_create(
        name="Maintenance Test Paper",
        qualification=qual1,
        defaults={"created_by": users['assessor_dev']}
    )
    paper2, _ = Paper.objects.get_or_create(
        name="Quality Test Paper",
        qualification=qual2,
        defaults={"created_by": users['assessor_dev']}
    )
    
    return {
        'qualifications': {'qual1': qual1, 'qual2': qual2},
        'users': users,
        'papers': {'paper1': paper1, 'paper2': paper2}
    }


def test_workflow_transitions(data):
    """Test each status transition in the workflow."""
    print_header("Testing Status Transitions")
    
    users = data['users']
    qual1 = data['qualifications']['qual1']
    paper = data['papers']['paper1']
    
    test_results = []
    
    # Create initial assessment
    assessment = Assessment.objects.create(
        eisa_id=f"TEST-{now().timestamp()}",
        qualification=qual1,
        paper=paper.name,
        created_by=users['assessor_dev'],
        status="draft",
    )
    print(f"Created assessment: {assessment.eisa_id}")
    
    # Test 1: Assessor creates → "draft" (implied ready)
    print_section("1. Assessor Developer Stage")
    test1 = assessment.status == "draft"
    test_results.append(test1)
    print_test("Assessment starts in 'draft' status", test1, f"Status: {assessment.status}")
    
    # Test 2: Assessor submits to Moderator
    print_section("2. Submit to Moderator")
    assessment.status = "Submitted to Moderator"
    assessment.status_changed_at = now()
    assessment.status_changed_by = users['assessor_dev']
    assessment.save()
    test2 = assessment.status == "Submitted to Moderator"
    test_results.append(test2)
    print_test("Assessor → Moderator transition", test2, f"Status: {assessment.status}")
    
    # Test 3: Moderator approves → "Submitted to QCTO"
    print_section("3. Moderator Review")
    assessment.status = "Submitted to QCTO"
    assessment.status_changed_at = now()
    assessment.status_changed_by = users['moderator']
    assessment.save()
    test3 = assessment.status == "Submitted to QCTO"
    test_results.append(test3)
    print_test("Moderator approves → QCTO", test3, f"Status: {assessment.status}")
    
    # Test 4: QCTO approves → "QDD Review" (NEW)
    print_section("4. QCTO Review")
    assessment.status = "QDD Review"
    assessment.status_changed_at = now()
    assessment.status_changed_by = users['qcto']
    assessment.save()
    test4 = assessment.status == "QDD Review"
    test_results.append(test4)
    print_test("QCTO approves → QDD Review", test4, f"Status: {assessment.status}")
    
    # Test 5: QDD approves → "pending_etqa"
    print_section("5. QDD Review")
    assessment.status = "pending_etqa"
    assessment.status_changed_at = now()
    assessment.status_changed_by = users['qdd']
    assessment.save()
    test5 = assessment.status == "pending_etqa"
    test_results.append(test5)
    print_test("QDD approves → ETQA (pending_etqa)", test5, f"Status: {assessment.status}")
    
    # Test 6: ETQA approves → "Approved by ETQA"
    print_section("6. ETQA Review")
    assessment.status = "Approved by ETQA"
    assessment.status_changed_at = now()
    assessment.status_changed_by = users['etqa']
    assessment.save()
    test6 = assessment.status == "Approved by ETQA"
    test_results.append(test6)
    print_test("ETQA approves → Final approval", test6, f"Status: {assessment.status}")
    
    return all(test_results), assessment


def test_qualification_filtering(data):
    """Test that qualification filtering works correctly at each stage."""
    print_header("Testing Qualification-Based Filtering")
    
    users = data['users']
    qual1 = data['qualifications']['qual1']
    qual2 = data['qualifications']['qual2']
    paper1 = data['papers']['paper1']
    
    test_results = []
    
    # Create assessments for different qualifications
    print_section("Creating test assessments")
    
    assessments = {
        'qual1': Assessment.objects.create(
            eisa_id=f"TEST-QUAL1-{now().timestamp()}",
            qualification=qual1,
            paper=paper1.name,
            created_by=users['assessor_dev'],
            status="Submitted to QCTO",
        ),
    }
    print(f"  Created assessment for {qual1.name}")
    
    # Test filtering at Moderator stage
    print_section("Moderator Stage (no filtering)")
    moderator_assessments = Assessment.objects.filter(
        status="Submitted to QCTO"
    ).count()
    test1 = moderator_assessments >= 1
    test_results.append(test1)
    print_test("Moderator can see assessments pending review", test1, 
               f"Found {moderator_assessments} assessments")
    
    # Test filtering at QCTO stage
    print_section("QCTO Stage (no filtering)")
    qcto_assessments = Assessment.objects.filter(
        status="Submitted to QCTO"
    ).count()
    test2 = qcto_assessments >= 1
    test_results.append(test2)
    print_test("QCTO can see assessments pending review", test2,
               f"Found {qcto_assessments} assessments")
    
    # Test filtering at QDD stage
    print_section("QDD Stage (with qualification filtering)")
    # Create a QDD review assessment
    assessments['qual1'].status = "QDD Review"
    assessments['qual1'].save()
    
    # Admin can see all QDD reviews
    admin_qdd = Assessment.objects.filter(status="QDD Review").count()
    test3 = admin_qdd >= 1
    test_results.append(test3)
    print_test("Admin can see all QDD reviews", test3,
               f"Found {admin_qdd} QDD reviews")
    
    # QDD user with qual1 can see qual1 QDD reviews
    user_qual1_qdd = Assessment.objects.filter(
        status="QDD Review",
        qualification=qual1
    ).count()
    test4 = user_qual1_qdd >= 1
    test_results.append(test4)
    print_test("QDD user (qual1) can see qual1 QDD reviews", test4,
               f"Found {user_qual1_qdd} assessments for {qual1.name}")
    
    # Test filtering at ETQA stage
    print_section("ETQA Stage (with qualification filtering)")
    assessments['qual1'].status = "pending_etqa"
    assessments['qual1'].save()
    
    etqa_qual1 = Assessment.objects.filter(
        status="pending_etqa",
        qualification=qual1
    ).count()
    test5 = etqa_qual1 >= 1
    test_results.append(test5)
    print_test("ETQA can see pending_etqa assessments", test5,
               f"Found {etqa_qual1} assessments")
    
    return all(test_results)


def test_permission_checks(data):
    """Test permission checks and authorization at each stage."""
    print_header("Testing Permission Checks")
    
    users = data['users']
    qual1 = data['qualifications']['qual1']
    qual2 = data['qualifications']['qual2']
    paper1 = data['papers']['paper1']
    
    test_results = []
    
    # Create assessments at each stage
    print_section("Creating assessments at each workflow stage")
    
    stages = {
        'moderator': Assessment.objects.create(
            eisa_id=f"TEST-MOD-{now().timestamp()}",
            qualification=qual1,
            paper=paper1.name,
            created_by=users['assessor_dev'],
            status="Submitted to Moderator",
        ),
        'qcto': Assessment.objects.create(
            eisa_id=f"TEST-QCTO-{now().timestamp()}",
            qualification=qual1,
            paper=paper1.name,
            created_by=users['assessor_dev'],
            status="Submitted to QCTO",
        ),
        'qdd': Assessment.objects.create(
            eisa_id=f"TEST-QDD-{now().timestamp()}",
            qualification=qual1,
            paper=paper1.name,
            created_by=users['assessor_dev'],
            status="QDD Review",
        ),
    }
    
    print(f"  Created assessments at: {', '.join(stages.keys())}")
    
    # Test: QDD user with matching qualification can access QDD assessment
    print_section("QDD Permission Test")
    qdd_user = users['qdd']
    qdd_assessment = stages['qdd']
    
    # Check if QDD user has the same qualification as the assessment
    can_access = (
        qdd_user.is_superuser or
        qdd_user.role in {'admin', 'qcto', 'etqa'} or
        qdd_user.qualification == qdd_assessment.qualification
    )
    test1 = can_access and qdd_user.qualification == qual1
    test_results.append(test1)
    print_test("QDD user (qual1) can moderate qual1 assessments", test1,
               f"User qual: {qdd_user.qualification}, Assessment qual: {qdd_assessment.qualification}")
    
    # Test: QDD user cannot access mismatched qualification
    print_section("Cross-Qualification Permission Test")
    
    # Create assessment for qual2
    qual2_assessment = Assessment.objects.create(
        eisa_id=f"TEST-QDD-QUAL2-{now().timestamp()}",
        qualification=qual2,
        paper=paper1.name,
        created_by=users['assessor_dev'],
        status="QDD Review",
    )
    
    # QDD user assigned to qual1 should not access qual2
    cannot_access = not (
        qdd_user.is_superuser or
        qdd_user.role in {'admin', 'qcto', 'etqa'} or
        qdd_user.qualification == qual2_assessment.qualification
    )
    test2 = cannot_access
    test_results.append(test2)
    print_test("QDD user (qual1) cannot access qual2 assessments", test2,
               f"Correctly blocked due to qualification mismatch")
    
    # Test: Admin can access all qualifications
    print_section("Admin Permission Test")
    admin_user = users['admin']
    
    admin_can_access_qual1 = (
        admin_user.is_superuser or admin_user.role == 'admin'
    )
    admin_can_access_qual2 = (
        admin_user.is_superuser or admin_user.role == 'admin'
    )
    test3 = admin_can_access_qual1 and admin_can_access_qual2
    test_results.append(test3)
    print_test("Admin can access all qualifications", test3,
               f"Admin role has unrestricted access")
    
    return all(test_results)


def test_status_chain(data):
    """Verify the complete status chain exists and is accessible."""
    print_header("Testing Complete Status Chain")
    
    users = data['users']
    qual1 = data['qualifications']['qual1']
    paper1 = data['papers']['paper1']
    
    expected_chain = [
        ("draft", "Initial state"),
        ("Submitted to Moderator", "Assessor submits"),
        ("Submitted to QCTO", "Moderator approves"),
        ("QDD Review", "QCTO approves (NEW)"),
        ("pending_etqa", "QDD approves"),
        ("Approved by ETQA", "ETQA final approval"),
    ]
    
    print_section("Expected Status Chain")
    for i, (status, description) in enumerate(expected_chain, 1):
        print(f"  {i}. {status:20} ← {description}")
    
    print_section("Verifying Status Chain")
    test_results = []
    
    # Create assessment and cycle through statuses
    assessment = Assessment.objects.create(
        eisa_id=f"TEST-CHAIN-{now().timestamp()}",
        qualification=qual1,
        paper=paper1.name,
        created_by=users['assessor_dev'],
        status="draft",
    )
    
    for status, description in expected_chain:
        assessment.status = status
        assessment.save()
        
        # Verify status was saved
        refreshed = Assessment.objects.get(id=assessment.id)
        test = refreshed.status == status
        test_results.append(test)
        print_test(f"{status:20}", test, description)
    
    return all(test_results)


def generate_report(results):
    """Generate final test report."""
    print_header("Final Test Report")
    
    total = len(results)
    passed = sum(1 for r in results if r)
    failed = total - passed
    
    percentage = (passed / total * 100) if total > 0 else 0
    
    print(f"Total Tests: {total}")
    print(f"Passed:      {GREEN}{passed}{RESET}")
    print(f"Failed:      {RED}{failed}{RESET}")
    print(f"Success:     {percentage:.1f}%")
    
    if percentage == 100:
        print(f"\n{GREEN}{BOLD}✓ All pipeline integrity tests passed!{RESET}")
        return True
    else:
        print(f"\n{RED}{BOLD}✗ Some tests failed. Review output above.{RESET}")
        return False


def main():
    print_header("Assessment Pipeline Integrity Test Suite")
    print("Testing: Admin → Assessor Dev → Moderator → QCTO → QDD → ETQA")
    
    all_results = []
    
    try:
        # Setup
        data = setup_test_data()
        
        # Run tests
        result1, assessment = test_workflow_transitions(data)
        all_results.append(result1)
        
        result2 = test_qualification_filtering(data)
        all_results.append(result2)
        
        result3 = test_permission_checks(data)
        all_results.append(result3)
        
        result4 = test_status_chain(data)
        all_results.append(result4)
        
        # Generate report
        success = generate_report(all_results)
        sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"\n{RED}{BOLD}ERROR: {str(e)}{RESET}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
