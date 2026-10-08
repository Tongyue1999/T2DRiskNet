$ErrorActionPreference = 'Stop'
$taskPython = 'C:\Users\HP\anaconda3\python.exe'
Set-Location -LiteralPath $PSScriptRoot
$taskScripts = @('extract_hospital_outcomes.py','verify_hospital_outcomes.py','complete_contact_dates.py','align_outcome_windows.py','extract_note_evidence.py','build_outcome_readiness.py','extract_diagnostic_sections.py','annotate_text_candidates.py','run_note_candidate_models.py')
foreach ($taskScript in $taskScripts) {
    & $taskPython $taskScript
    if ($LASTEXITCODE -ne 0) { throw "Outcome pipeline failed: $taskScript" }
}
