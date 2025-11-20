from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
import core.views as views
from core import admin_views as admin_pages
from core import extractor_views
from core.create_student import (toggle_student_status, create_student_by_assessment_center)
from core.auth_views import (forgot_password, reset_password)
# import core.oldviews as oldviews
    
urlpatterns = [
    # Admin URLs
    path('administrator/', views.admin_dashboard, name='admin_dashboard'),
    path('administrator/dashboards/', admin_pages.administrator_analytics_dashboard, name='administrator_dashboards'),
    path('administrator/paper-bank/', admin_pages.administrator_paperbank, name='administrator_paperbank'),
    path('administrator/user-management/', views.user_management, name='user_management'),
    path('administrator/qualifications/', views.qualification_management_view, name='manage_qualifications'),
    path('administrator/assessment-centres/', views.assessment_centres_view, name='assessment_centres'),
    path('administrator/review-saved/', views.review_saved_selector, name='review_saved_selector'),
    path('administrator/review-saved/<int:paper_pk>/', views.load_saved_paper_view, name='load_saved_paper'),
    path('administrator/traditional-pipeline/', extractor_views.upload_view, name='exam_upload'),
    path('administrator/traditional-pipeline/paper/<int:paper_id>/', extractor_views.paper_view, name='exam_paper'),
    path('papers/<int:paper_pk>/save-blocks/', views.save_blocks_view, name='save-blocks'),

    # Question Bank URLs
    path('databank/', views.databank_view, name='databank'),
    path('add-question/', views.add_question, name='add_question'),
    path('add-case-study/', views.add_case_study, name='add_case_study'),
    
    # User Management URLs
    path('update-user-role/<int:user_id>/', views.update_user_role, name='update_user_role'),
    path('update-user-qualification/<int:user_id>/', views.update_user_qualification, name='update_user_qualification'),
    path('toggle-user-status/<int:user_id>/', views.toggle_user_status, name='toggle_user_status'),

    # Assessment Centre URLs
    path('edit-centre/<int:centre_id>/', views.edit_assessment_centre, name='edit_assessment_centre'),
    path('delete-centre/<int:centre_id>/', views.delete_assessment_centre, name='delete_assessment_centre'),
    path('upload-register/', views.upload_student_register, name='upload_student_register'),
    path('download-template/', views.download_register_template, name='download_register_template'),
    path('upload-offline-exam/', views.upload_offline_exam_submission, name='upload_offline_exam'),
    path('quick-grade/<int:submission_id>/', views.quick_grade_submission, name='quick_grade_submission'),

    # Assessor URLs
    path('assessor/', views.assessor_dashboard, name='assessor_dashboard'),
    path('assessor/upload/', views.upload_assessment, name='upload_assessment'),
    path('assessor/reports/', views.assessor_reports, name='assessor_reports'),
    path('assessor/archive/', views.assessment_archive, name='assessment_archive'),
    path('assessor/view/<str:eisa_id>/', views.view_assessment, name='view_assessment'),
    path('assessor-developer/', views.assessor_developer, name='assessor_developer'),
    path('assessor-developer/pools.json', views.assessor_pool_data, name='assessor_pool_data'),
    path('assessor-developer/pools/randomize/', views.assessor_pool_randomize, name='assessor_pool_randomize'),
    path('assessor-developer/randomized/<int:assessment_id>/', views.assessor_randomized_snapshot, name='assessor_randomized_snapshot'),
    path('assessor-developer/paper/<int:paper_id>/', views.assessor_developer_paper, name='assessor_developer_paper'),
    path('assessor-developer/paper/<int:paper_id>/autoclassify/', extractor_views.autoclassify, name='exam_autoclassify'),
    path('assessor-developer/paper/<int:paper_id>/boxes/create/', extractor_views.create_box, name='exam_create_box'),
    path('assessor-developer/paper/<int:paper_id>/boxes/<int:box_id>/update/', extractor_views.update_box, name='exam_update_box'),
    path('assessor-developer/paper/<int:paper_id>/boxes/<int:box_id>/delete/', extractor_views.delete_box, name='exam_delete_box'),
    path('assessor-developer/paper/<int:paper_id>/boxes/<int:box_id>/json/', extractor_views.get_box, name='exam_get_box'),
    path('assessor-developer/paper/<int:paper_id>/ai/draw_blocks/', extractor_views.ai_draw_blocks, name='exam_ai_draw_blocks'),
    path('assessor-developer/paper/<int:paper_id>/images/convert_emf/', extractor_views.convert_emf, name='exam_convert_emf'),
    path('assessor-developer/paper/<int:paper_id>/bank/info/', extractor_views.bank_info, name='exam_bank_info'),
    path('assessor-developer/paper/<int:paper_id>/bank/preview/', extractor_views.bank_preview, name='exam_bank_preview'),
    path('assessor-developer/paper/<int:paper_id>/bank/randomize/', extractor_views.randomize_test, name='exam_randomize_test'),
    path('assessor-developer/paper/<int:paper_id>/mbalaka/markdown/', extractor_views.mbalaka_markdown, name='exam_mbalaka_markdown'),
    path('assessor-developer/paper/<int:paper_id>/mbalaka/classify/', extractor_views.mbalaka_classify, name='exam_mbalaka_classify'),
    path('assessor-developer/paper/<int:paper_id>/delimit/', extractor_views.delimit_rubric, name='exam_delimit_rubric'),
    path('assessor-developer/paper/<int:paper_id>/system_prompt/save/', extractor_views.save_system_prompt, name='exam_save_system_prompt'),
    path('assessor-developer/paper/<int:paper_id>/meta/save/', extractor_views.save_paper_meta, name='exam_save_paper_meta'),
    path('assessor-developer/test/<int:test_id>/', extractor_views.view_test, name='exam_view_test'),
    path('download-randomized/<int:assessment_id>/', views.download_randomized_pdf, name='download_randomized_pdf'),
    # Moderator URLs
    path('moderator/', views.moderator_developer_dashboard, name='moderator_developer'),
    path('moderate/<str:eisa_id>/', views.moderate_assessment, name='moderate_assessment'),
    path('add-feedback/<str:eisa_id>/', views.add_feedback, name='add_feedback'),
    path('moderator/reports/', views.moderator_reports, name='moderator_reports'),
    path('moderator/review-list/', views.moderator_review_list, name='moderator_review_list'),
    path('moderator/approve-reject/', views.moderator_approve_reject, name='moderator_approve_reject'),
    path('moderator/feedback/', views.moderator_feedback, name='moderator_feedback'),
    path('moderator/history/', views.moderator_history, name='moderator_history'),
    path('moderator/download-report/<str:eisa_id>/', views.download_moderator_report, name='download_moderator_report'),

    # ETQA URLs
    path('etqa/', views.etqa_dashboard, name='etqa_dashboard'),
    path('etqa/assessment/', views.etqa_assessment_view, name='etqa_assessment_view'),
    path('etqa/toggle/<int:assessment_id>/', views.toggle_selection_by_etqa, name='toggle_selection_by_etqa'),
    path('etqa/release/<int:assessment_id>/', views.release_assessment_to_students, name='release_assessment_to_students'),
    path('submit-to-center/<int:batch_id>/', views.submit_to_center, name='submit_to_center'),
    path('achieved-assessments/', views.achieved_assessments_view, name='achieved_assessments'),
    path('download-memo/<int:assessment_id>/', views.download_memo, name='download_memo'),

    path('internal-moderator/dashboard/', views.internal_moderator_dashboard, name='internal_moderator_dashboard'),
    path('external-moderator/dashboard/', views.external_moderator_dashboard, name='external_moderator_dashboard'),
    path('internal-moderator/grade/<int:submission_id>/', views.internal_grade_submission, name='internal_grade_submission'),
    path('external-moderator/grade/<int:submission_id>/', views.external_grade_submission, name='external_grade_submission'),


    # QCTO URLs
    path('qcto/', views.qcto_dashboard, name='qcto_dashboard'),
    path('qcto/moderate/<str:eisa_id>/', views.qcto_moderate_assessment, name='qcto_moderate_assessment'),
    path('qcto/reports/', views.qcto_reports, name='qcto_reports'),
    path('qcto/compliance/', views.qcto_compliance, name='qcto_compliance'),
    path('qcto/review/', views.qcto_assessment_review, name='qcto_assessment_review'),
    path('qcto/archive/', views.qcto_archive, name='qcto_archive'),
    path('qcto/view/<str:eisa_id>/', views.qcto_view_assessment, name='qcto_view_assessment'),

    # Authentication URLs
    path('', views.custom_login, name='custom_login'),
    path('logout/', views.custom_logout, name='logout'),  # Change name from 'custom_login' to 'logout'
    path('register/', views.register, name='register'),
    path('default/', views.default_page, name='default'),
    path('waiting-activation/', views.waiting_activation, name='waiting_activation'),

    # Student URLs
    path('student/', views.student_dashboard, name='student_dashboard'),
    path('student/approved-assessments/', views.approved_assessments_for_learners, name='approved_assessments_for_learners'),
    path('student/assessments/<int:assessment_id>/write/', views.write_exam, name='write_exam'),
    path('student/assessments/<int:assessment_id>/submit/', views.submit_exam, name='submit_exam'),
    path('paper/<int:paper_id>/register/', views.student_registration, name='student_registration'),
    ################################################################################################################
    path('toggle-student-status/<int:student_id>/', views.toggle_student_status, name='toggle_student_status'),


###############################################################################################################    

   # path('create-batch/', create_batch, name='create_batch'),
    path('assessment-center/', views.assessment_center_view, name='assessment_center'), 
    path('assessment-center/create-student/', create_student_by_assessment_center, name='create_student_by_assessment_center'), 
   #############################################################################################################################  
    #Demo Student URLS to be robusted later
    path('student/papers/', views.papers_demo, name='papers_demo'),
    path('student/papers/<int:paper_id>/write/', views.write_paper_simple, name='write_paper_simple'),
    path('student/papers/<int:paper_id>/submit/', views.submit_paper_simple, name='submit_paper_simple'),
    

    # Tracking URLs
    path('track/', views.assessment_progress_tracker, name='assessment_progress_tracker'),

    # Randomize Paper Structure URL
    path('randomize/paper/<int:paper_pk>/', 
         views.randomize_paper_structure_view, 
         name='randomize_paper_structure'),

    # Save Blocks URL
  # urls.py
    path('save-blocks/<int:paper_id>/', views.save_blocks_view, name='save_blocks'),

# Forgot password view
    path('forgot-password/', forgot_password, name='forgot_password'),
    path('reset-password/<uidb64>/<token>/', reset_password, name='reset_password'),

  # redirections for assessor marker
    path('assessor_marker/dashboard/', views.assessor_maker_dashboard, name='assessor_maker_dashboard'),
    path('student/results/', views.student_results, name='student_results'),
    path('upload-marked-paper/<int:submission_id>/', views.upload_marked_paper, name='upload_marked_paper'),

    ############nNEW URLS#########################################
   path("upload/", extractor_views.upload_view, name="exam_upload_generic"),

    # Paper detail and actions
    path("paper/<int:paper_id>/", extractor_views.paper_view, name="exam_paper"),
    path(
        "paper/<int:paper_id>/autoclassify/",
        extractor_views.autoclassify,
        name="exam_autoclassify",
    ),
    path(
        "paper/<int:paper_id>/boxes/create/",
        extractor_views.create_box,
        name="exam_create_box",
    ),
    path(
        "paper/<int:paper_id>/boxes/<int:box_id>/update/",
        extractor_views.update_box,
        name="exam_update_box",
    ),
    # AI helpers
    path(
        "paper/<int:paper_id>/ai/draw_blocks/",
        extractor_views.ai_draw_blocks,
        name="exam_ai_draw_blocks",
    ),
    path(
        "paper/<int:paper_id>/boxes/<int:box_id>/delete/",
        extractor_views.delete_box,
        name="exam_delete_box",
    ),
    path(
        "paper/<int:paper_id>/boxes/<int:box_id>/json/",
        extractor_views.get_box,
        name="exam_get_box",
    ),
    path(
        "paper/<int:paper_id>/images/convert_emf/",
        extractor_views.convert_emf,
        name="exam_convert_emf",
    ),
    # Question bank + test assembly
    path(
        "paper/<int:paper_id>/bank/info/",
        extractor_views.bank_info,
        name="exam_bank_info",
    ),
    path(
        "paper/<int:paper_id>/bank/preview/",
        extractor_views.bank_preview,
        name="exam_bank_preview",
    ),
    path(
        "paper/<int:paper_id>/bank/randomize/",
        extractor_views.randomize_test,
        name="exam_randomize_test",
    ),
    path(
        "test/<int:test_id>/",
        extractor_views.view_test,
        name="exam_view_test",
    ),
    # Mbalaka: Markdown + LLM classification
    path(
        "paper/<int:paper_id>/mbalaka/markdown/",
        extractor_views.mbalaka_markdown,
        name="exam_mbalaka_markdown",
    ),
    path(
        "paper/<int:paper_id>/mbalaka/classify/",
        extractor_views.mbalaka_classify,
        name="exam_mbalaka_classify",
    ),
    path(
        "paper/<int:paper_id>/delimit/",
        extractor_views.delimit_rubric,
        name="exam_delimit_rubric",
    ),
    path(
        "paper/<int:paper_id>/system_prompt/save/",
        extractor_views.save_system_prompt,
        name="exam_save_system_prompt",
    ),
    path(
        "paper/<int:paper_id>/meta/save/",
        extractor_views.save_paper_meta,
        name="exam_save_paper_meta",
    ),

]

# if settings.DEBUG:
#     urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
