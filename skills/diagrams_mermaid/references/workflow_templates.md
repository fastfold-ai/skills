# Workflow Templates

These templates are starting points. Adapt names and steps to the user's request.

## 1) BoltzGen Design Pipeline (Flowchart)

```mermaid
flowchart TD
    userGoal[UserGoal] --> prepInputs[PrepareInputs]
    prepInputs --> createDraft[CreateWorkflowDraft]
    createDraft --> uploadFiles[UploadDesignSpecAndStructures]
    uploadFiles --> upsertGraph[UpsertWorkflowGraph]
    upsertGraph --> reviewDraft[ReviewComposerDraft]
    reviewDraft --> executeRun[ExecuteWorkflow]
    executeRun --> waitStatus[WaitForTerminalStatus]
    waitStatus --> fetchResults[FetchRankedCandidatesAndMetrics]
    fetchResults --> shareOutputs[ShareLinksAndSummary]
```

## 2) Fold to MD Chain (Flowchart)

```mermaid
flowchart LR
    submitFold[SubmitFoldJob] --> foldComplete{FoldCompleted}
    foldComplete -->|No| waitFold[PollFoldStatus]
    waitFold --> foldComplete
    foldComplete -->|Yes| choosePath{SelectDownstreamPath}
    choosePath -->|OpenMMCalvados| runCalvados[RunOpenMMCalvadosWorkflow]
    choosePath -->|OpenMMDL| runOpenmmdl[RunOpenMMDLWorkflow]
    runCalvados --> collectArtifacts[CollectArtifactsAndMetrics]
    runOpenmmdl --> collectArtifacts
    collectArtifacts --> reportSummary[ReportResults]
```

## 3) Agent-Orchestrated Multi-Step Execution (Sequence)

```mermaid
sequenceDiagram
    participant User
    participant Agent
    participant Skills
    participant Api
    participant Sandbox

    User->>Agent: RequestComplexWorkflow
    Agent->>Skills: SelectRelevantSkill
    Agent->>Api: CreateOrAttachThread
    Agent->>Sandbox: ExecuteSkillScripts
    Sandbox->>Api: SubmitAndPollRun
    Api-->>Sandbox: StatusAndArtifacts
    Sandbox-->>Agent: StructuredResults
    Agent-->>User: SummaryAndDiagram
```

## 4) Research/Analysis Decision Flow (Flowchart)

```mermaid
flowchart TD
    parseQuestion[ParseQuestion] --> needData{NeedAdditionalData}
    needData -->|Yes| gatherData[GatherData]
    needData -->|No| analyze[AnalyzeAvailableContext]
    gatherData --> validateData[ValidateAndNormalize]
    validateData --> analyze
    analyze --> sufficientConfidence{SufficientConfidence}
    sufficientConfidence -->|No| refinePlan[RefinePlanAndCollectMore]
    refinePlan --> gatherData
    sufficientConfidence -->|Yes| deliverAnswer[DeliverAnswer]
```
