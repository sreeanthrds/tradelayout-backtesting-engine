flowchart TB

    %% MARKET DATA SOURCES
    MDS["MARKET DATA SOURCES
    Stocks | Forex | Crypto | Futures | Options"]

    %% SYMBOL SUBSCRIBER
    SS["SYMBOL SUBSCRIBER
    Subscribes to multiple instruments simultaneously"]

    %% TICK NORMALIZER
    TN["TICK NORMALIZER
    Converts raw ticks → unified event format"]

    %% MULTI-STRATEGY DISPATCHER
    MSD["MULTI-STRATEGY DISPATCHER
    Single/multiple users running multiple strategies
    Each strategy selects symbols it needs"]

    %% MULTI-ASSET/MULTI-SYMBOL ROUTER
    MASR["MULTI-ASSET / MULTI-SYMBOL ROUTER
    Routes normalized ticks to per-symbol processors"]

    %% FIVE PROCESSORS
    subgraph PROC[" "]
        direction LR
        EP["EQUITY PROCESSOR\nper symbol"]
        FP["FOREX PROCESSOR\nper pair"]
        CP["CRYPTO PROCESSOR\nper pair"]
        FUP["FUTURES PROCESSOR\nper contract"]
        OP["OPTIONS PROCESSOR\nper contract"]
    end

    %% CONTEXT STORE / INDICATOR ENGINE
    CS["CONTEXT STORE / INDICATOR ENGINE
    Shared indicators: SMA, EMA, RSI, custom nodes"]

    %% EXECUTION ENGINE
    EE["EXECUTION ENGINE (Backend)"]

    %% CONNECTIONS
    MDS --> SS --> TN --> MSD --> MASR --> PROC --> CS --> EE

    %% STYLE
    classDef box fill:#ffffff,stroke:#000000,stroke-width:1px,color:#000000;
    class MDS,SS,TN,MSD,MASR,EP,FP,CP,FUP,OP,CS,EE box;