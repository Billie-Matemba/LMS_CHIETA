# ...existing imports and patterns...

urlpatterns = [
    # ...existing patterns...
    
    # Developer dashboard (with memo randomisation partial)
    path('developer/', views.assessor_developer, name='assessor_developer'),
    
    # Randomisation submission
    path('randomise-paper-with-memo/', views.randomise_paper_with_memo, name='randomise_paper_with_memo'),
    
    # Memo randomisation developer view
    path(
        'developer/paper/<str:paper_id>/qualification/<str:qualification_id>/memo-randomisation/',
        views.assessor_developer_memo_randomisation,
        name='assessor_developer_memo_randomisation'
    ),
    path('paper/<str:paper_id>/memo/', views.view_paper_memo, name='view_paper_memo'),
    path('paper/<str:paper_id>/memo/download/', views.download_paper_memo_pdf, name='download_paper_memo_pdf'),
    path('paper/<str:paper_id>/', views.view_paper, name='view_paper'),

    # Randomised papers CRUD
    path('developer/randomized/', views.randomised_papers_list, name='randomised_papers_list'),
    path('developer/randomized/<str:paper_id>/memo/', views.randomised_paper_memo_crud, name='randomised_paper_memo_crud'),
    path('developer/randomized/<str:paper_id>/memo/save/<str:node_id>/', views.save_question_memo, name='save_question_memo'),
    path('developer/randomized/<str:paper_id>/memo/delete/<str:node_id>/', views.delete_question_memo, name='delete_question_memo'),
    path('developer/randomized/<str:paper_id>/memo/convert/<str:node_id>/', views.convert_question_to_memo, name='convert_question_to_memo'),
    path('developer/randomized/<str:paper_id>/memo/update-block/<str:node_id>/', views.update_question_block, name='update_question_block'),
    path('developer/randomized/<str:paper_id>/memo/finalize/', views.finalize_randomised_paper_memo, name='finalize_randomised_paper_memo'),
    path('developer/randomized/<str:paper_id>/memo/view/', views.view_randomised_paper_memo, name='view_randomised_paper_memo'),
    path('developer/randomized/<str:paper_id>/memo/download/', views.download_randomised_paper_memo_pdf, name='download_randomised_paper_memo_pdf'),
    path('developer/randomized/<str:paper_id>/delete/', views.delete_randomised_paper, name='delete_randomised_paper'),
]
