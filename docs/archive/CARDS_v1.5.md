# Overload Party v1.6 — Card List

**全 119 枚**

---

## 凡例

- 数値は **small (Rank 1)** 基準
- **(R)** = Resizable, **(E)** = Elastic, **(R+E)** = 両方
- Elastic カードは「base→上限」で表記
- **TP** = Throughput（攻撃力 兼 Revenue 変換上限）
- **AV** = Availability（耐久値。0 で破壊）
- **DV** = DV Gen（Data Value 生成量/turn）
- **Request Cost** = 攻撃するたびに支払う Budget
- **Deploy Cost** = カードを場に出す / Scale Up するときの Budget
- **SLA Penalty** = カード破壊時にオーナーの Budget から強制減算
- **制限** = リポジトリ投入上限（**原則 3枚**。制限カードのみ下表に記載）

### 制限カード（1枚制限）

| カード名 | 理由 |
|---------|------|
| Cloud Engineer | Miracle カードをトラッシュに送る特殊効果 |
| Cloud Architect | Miracle カードをトラッシュに送る特殊効果 |
| Terakoya | 陣営不問のサーチは強力すぎる |
| Ransomware | 1ターン完全停止は壊滅的 |

### 準制限カード（2枚制限）

| カード名 | 理由 |
|---------|------|
| BingoQuery | DV 700 + Streaming Insert で経済が壊れる |
| Miracle APEX | Dep 0 / RC 0 の完全無料フロントエンド |

**上記以外のカードはすべて 3枚まで投入可能。**

---

## SWS（Smile Web Services）— 24枚

### Frontend（5枚）

| # | カード名 | タイプ | TP | AV | Request Cost | Deploy Cost | SLA Penalty | 効果 | 元ネタ |
|---|---------|-------|-----|-----|-----|-----|-----|------|----------|
| 1 | えくぼ | Compute (R) | 700 | 1400 | 200 | 400 | 400 | — | EC2 |
| 3 | Egao Container | Container (E) | 500→1100 | 1200 | 400 | 300 | 400 | — | ECS/Fargate |
| 4 | Komodoensis | Orchestrator (R+E) | 600→1000 | 1500 | 200 | 600 | 600 | — | EKS |
| 5 | Laugh Maker | AI/ML (R) | 1100 | 1000 | 400 | 700 | 600 | — | SageMaker |
| 6 | ラム | Serverless (E) | 500→1000 | 1200 | 0 | 100 | 200 | **S3 Trigger:** 自分のフィールドに SWS Storage がいる時に発動する。このカードの TP を +200 する | Lambda |

### Backend（6枚）

| # | カード名 | タイプ | DV | AV | Deploy Cost | SLA Penalty | 効果 | 元ネタ |
|---|---------|-------|-----|-----|-----|-----|------|----------|
| 7 | Smile RDS | Database (R) | 500 | 1300 | 400 | 500 | **Reserved Instance (Optional):** Deploy 時に発動できる。このカードの Deploy Cost を -200 する。ただし、この効果を使用して Deploy した場合、他の Component を Deploy するためにこのカードをトラッシュすることはできない。 | RDS |
| 8 | Smile Aurora | Database (R) | 500 | 1200 | 600 | 500 | **Aurora Cluster:** 自分のフィールドのこのカード以外の SWS の DB 1体につき、このカードの DV Gen を +200 する | Aurora |
| 9 | えすす | Storage | 300 | 1800 | 100 | 300 | **Versioning:** 自分のフィールドの SWS のバックエンドが破壊された時に発動できる。そのカードを自分の手札に戻す。 | S3 |
| 10 | Daikichi | NoSQL (E) | 300→800 | 1600 | 300 | 400 | **On-Demand:** Budget 400 を払って発動できる。このターン、このカードの DV Gen を2倍にする。この効果は1ターン中に1回のみ使用できる | DynamoDB |
| 11 | Egao Cache | Cache DB (R) | 200 | 1100 | 200 | 100 | **Cache Engine:** デプロイ時に選択 — **Memcached:** Budget +400 / **Redis:** DV Gen +200（永続） | ElastiCache |
| 124 | Smile Duck | Cache DB (R) | 200 | 1200 | 200 | 100 | **DAX Accelerator:** 場に Daikichi がいる時、Daikichi の DV Gen +200 | DAX |

### Platform（4枚）

| # | カード名 | 種別 | 効果 | 元ネタ |
|---|---------|------|------|----------|
| 12 | Smile Pipeline | CI/CD | SWS の Scale Up コスト -200（最低 0） | CodePipeline |
| 13 | Smile Front | Network | SWS フロントエンド全体の TP +200 | CloudFront |
| 14 | Smile Guard | Security (Detect) | 相手の伏せ Trap 1枚を確認 | GuardDuty |
| 15 | Smile Firewall | Security (Block) | DDoS Attack / Data Breach を無効化 | WAF |

### Attachment（3枚）

| # | カード名 | 装備先 | 効果 | 元ネタ |
|---|---------|-------|------|----------|
| 16 | Smile Queue | Compute 系 | **Message Queue:** Revenue Phase で変換しきれなかった DV を最大 600 まで次ターンに繰り越し | SQS |
| 17 | Smile Gateway | Compute / Serverless | **API 管理:** TP +200 | API Gateway |
| 18 | Smile KMS | DB / Storage | **暗号化:** Data Breach を無効化 | KMS |

### Strategy（5枚）

| # | カード名 | Cost | 効果 | 元ネタ |
|---|---------|------|------|----------|
| 19 | Smile Formation | 200 | リポジトリから SWS Component 1枚を手札に加える | CloudFormation |
| 20 | Smile Marketplace | 0 | 場に SWS カード 3枚以上なら Budget +600 | AWS Marketplace |
| 21 | Smile Cost Explorer | 0 | このターンの全 Deploy Cost -200（最低 0） | Cost Explorer |
| 118 | Smile Ecosystem | 0 | 場に SWS カード 3枚以上の時使用可能。このターン、SWS フロントエンド全体の TP +200 | AWS Ecosystem |
| 121 | Prime Delivery | 200 | 手札のカード 1枚を選び、即座に Deploy Cost 0 で場に出す | Amazon Prime |

### Trap（1枚）

| # | カード名 | 発動条件 | 効果 | 元ネタ |
|---|---------|---------|------|----------|
| 22 | Smile Recovery | 自分の SWS Component の AV が 400 以下になった時 | その Component の AV +500 | Auto Recovery |

---

## Aozora（Aozora Cloud）— 26枚

### Frontend（6枚）

| # | カード名 | タイプ | TP | AV | Request Cost | Deploy Cost | SLA Penalty | 効果 | 元ネタ |
|---|---------|-------|-----|-----|-----|-----|-----|------|----------|
| 23 | Aozora VM | Compute (R) | 600 | 1700 | 200 | 500 | 400 | — | Azure VM |
| 24 | Aozora App Service | Compute (R) | 400 | 1500 | 100 | 100 | 400 | **Auto Patch:** Incident ダメージ -200 | App Service |
| 25 | Aozora Container | Container (E) | 600→1200 | 1300 | 400 | 300 | 400 | — | ACI |
| 26 | Kaleidoscope | Orchestrator (R+E) | 600→1000 | 1800 | 200 | 600 | 700 | — | AKS |
| 27 | Aozora Opener | AI/ML (R) | 900 | 1200 | 400 | 700 | 600 | **On Your Data:** 自分の Aozora バックエンド DB 1体につき TP +200 | Azure OpenAI |
| 28 | Aozora Functions | Serverless (E) | 400→800 | 1300 | 0 | 100 | 200 | — | Azure Functions |

### Backend（5枚）

| # | カード名 | タイプ | DV | AV | Deploy Cost | SLA Penalty | 効果 | 元ネタ |
|---|---------|-------|-----|-----|-----|-----|------|----------|
| 29 | Aozora SQL | Database (R) | 500 | 1400 | 400 | 500 | — | Azure SQL |
| 30 | SQL Supercell | Database (R) | 500 | 1400 | 600 | 500 | **Failover Group:** 場の他の Aozora DB が破壊された時、DV Gen +400（2ターン持続） | SQL Hyperscale |
| 31 | Aozora Blob | Storage | 200 | 2100 | 100 | 300 | — | Azure Blob |
| 32 | UniverseDB | NoSQL (E) | 300→900 | 1100 | 400 | 500 | **Multi-Model:** DB 2つ分としてカウントする（カード効果の DB 参照時に2体分）<br>**Turnkey Global Distribution:** デプロイ時、リポジトリから UniverseDB 1枚を Deploy Cost 0 で即デプロイできる。この効果は1ターン中に1回のみ使用できる | CosmosDB |
| 33 | Aozora Cache | Cache DB (R) | 200 | 1500 | 200 | 100 | — | Azure Cache for Redis |

### Platform（4枚）

| # | カード名 | 種別 | 効果 | 元ネタ |
|---|---------|------|------|----------|
| 34 | Aozora DevOps | CI/CD | Aozora の Scale Up コスト -200（最低 0） | Azure DevOps |
| 35 | Aozora CDN | Network | Aozora フロントエンド全体の TP +200 | Azure CDN |
| 36 | Madonosoft Sentinel | Security (Detect) | 相手の伏せ Trap 1枚を確認し、Incident ダメージを -300 する | Microsoft Sentinel |
| 37 | Aozora Protection | Security (Block) | DDoS Attack / Data Breach を無効化 | Azure DDoS Protection |

### Attachment（4枚）

| # | カード名 | 装備先 | 効果 | 元ネタ |
|---|---------|-------|------|----------|
| 38 | Aozora Backup | Component | **復元:** 破壊時、次の自分ターンに AV 半分（端数切上を200単位）で場に戻る（Deploy Cost 不要）。この効果は1ゲーム中に1回のみ使用できる | Azure Backup |
| 39 | Aozora Entra | Component | **認証基盤:** 装備先への Incident ダメージ -200 | Entra ID |
| 40 | Aozora Key Vault | DB / Storage | **Secret 管理:** Data Breach を無効化 | Key Vault |
| 41 | Aozora Site Recovery | Component | **DR:** 破壊時、リポジトリからコピーを AV 200 で即デプロイ（Deploy Cost 0）。この効果は1ゲーム中に1回のみ使用できる | Site Recovery |

### Strategy（3枚）

| # | カード名 | Cost | 効果 | 元ネタ |
|---|---------|------|------|----------|
| 42 | Aozora Template | 200 | リポジトリから Aozora Component 1枚を手札に加える | ARM Templates |
| 43 | Aozora Migration | 100 | トラッシュから Component 1枚を手札に戻す | Azure Migrate |
| 44 | Aozora Policy | 400 | このターン、相手は Incident を使用できない | Azure Policy |

### Trap（4枚）

| # | カード名 | 発動条件 | 効果 | 元ネタ |
|---|---------|---------|------|----------|
| 45 | Madonosoft Defender | 相手が Incident 使用時 | その Incident を完全無効化 | Microsoft Defender |
| 46 | Aozora Traffic | 自分の Aozora フロントエンド破壊時 | 手札から Aozora Compute 系 1枚を Deploy Cost 0 で即配置 | Traffic Manager |
| 123 | Windy Update | 相手が攻撃宣言した時 | Aozora 属性のカードすべてに 400 ダメージを与える | Windows Update |
| 122 | Madonosoft Failer | 相手のメインフェイズ開始時 | このターン、Aozora (Azure) 属性のフロントエンド全員は攻撃できない | — |

---

## Guruguru — 23枚

### Frontend（7枚）

| # | カード名 | タイプ | TP | AV | Request Cost | Deploy Cost | SLA Penalty | 効果 | 元ネタ |
|---|---------|-------|-----|-----|-----|-----|-----|------|----------|
| 47 | Guruguru Compute | Compute (R) | 900 | 1100 | 200 | 300 | 400 | — | GCE |
| 48 | Guruguru Spot | Compute (R) | 800 | 900 | 200 | 100 | 100 | **Spot Instance:** デプロイから 2ターン後の End Phase に自動破壊（SLA Penalty 適用） | Spot VM |
| 49 | Guruguru Run | Container (E) | 700→1500 | 1200 | 400 | 200 | 200 | **Scale to Zero:** 攻撃しなかったターンの次、RC 0 | Cloud Run |
| 50 | Kindergarten | Orchestrator (R+E) | 700→1100 | 1300 | 200 | 600 | 600 | **Autopilot:** デプロイ時、即座に medium にスケールアップ（Scale Cost 不要）<br>**Fleet:** 自分の場に他の Guruguru Orchestrator がいる時、このカードの Deploy Cost 0 | GKE |
| 51 | Veloce AI | AI/ML (R) | 1300 | 900 | 500 | 700 | 600 | **Training Pipeline:** 攻撃時、相手の DV を 400 奪う | Vertex AI |
| 52 | Guruguru Tensor | AI/ML (R) | 1700 | 800 | 700 | 1000 | 800 | **Training Pipeline:** 攻撃時、相手の DV を 600 奪う<br>**Cascade Failure:** 破壊時、自分のバックエンド全体に 400 ダメージを与える | Cloud TPU |
| 53 | Guruguru Run Functions | Serverless (E) | 700→1100 | 1000 | 0 | 100 | 200 | — | Cloud Functions |

### Backend（6枚）

| # | カード名 | タイプ | DV | AV | Deploy Cost | SLA Penalty | 効果 | 元ネタ |
|---|---------|-------|-----|-----|-----|-----|------|----------|
| 54 | Guruguru SQL | Database (R) | 500 | 1000 | 300 | 400 | — | Cloud SQL |
| 55 | Guruguru Snapper | Database (E) | 500→700 | 1300 | 600 | 600 | **Global Consistency:** Incident の対象にならない | Cloud Spanner |
| 56 | Guruguru Storage | Storage | 300 | 1400 | 100 | 200 | — | GCS |
| 57 | Fiberstore | NoSQL (E) | 300→800 | 1400 | 300 | 400 | **Realtime Sync:** 自分が Guruguru Component をデプロイするたびに追加 DV +200（DV プールに加算） | Firestore |
| 58 | BingoQuery | Database | 700 | 1100 | 300 | 400 | **Streaming Insert:** 自分の Guruguru フロントエンドが攻撃するたび、追加 DV +200 をプールに加算 | BigQuery |
| 125 | Guruguru Cache | Cache DB (R) | 200 | 1200 | 200 | 100 | **Cache Engine:** デプロイ時に選択 — **Memcached:** Budget +400 / **Redis:** DV Gen +200（永続） | Memorystore |

### Platform（3枚）

| # | カード名 | 種別 | 効果 | 元ネタ |
|---|---------|------|------|----------|
| 59 | Guruguru Build | CI/CD | Guruguru の Scale Up コスト -200（最低 0） | Cloud Build |
| 60 | Guruguru CDN | Network | Guruguru フロントエンド全体の TP +200 | Cloud CDN |
| 61 | BingoQuery Analytics | DV 奪取 | 毎ターン DV Generation Phase で、相手の DV を 300 奪う | BigQuery Analytics |

### Attachment（3枚）

| # | カード名 | 装備先 | 効果 | 元ネタ |
|---|---------|-------|------|----------|
| 62 | Guruguru Profiler | Compute 系 | **最適化:** TP +200 | Cloud Profiler |
| 63 | Guruguru Pub/Sub | Compute 系 | **Message Fanout:** 装備先が攻撃した時、場の他の自分の Guruguru フロントエンド 1体も同じ対象に 200 ダメージを与える（RC 不要、攻撃回数を消費しない） | Pub/Sub |
| 64 | Dangoflow | DB / Storage | **Stream Processing:** DV Gen +300。装備先の AV -100 | Dataflow |

### Strategy（3枚）

| # | カード名 | Cost | 効果 | 元ネタ |
|---|---------|------|------|----------|
| 65 | Guruguru Deployment | 200 | リポジトリから Guruguru Component 1枚を手札に加える | Deployment Manager |
| 66 | Veloce AI Batch | 300 | フロントエンド Compute 系 1体を選択。このターンその TP を 2倍にする（Battle + Revenue 両方） | Vertex AI Batch |
| 67 | Guruguru Knowledge | 100 | 相手の DV を 400 奪う。相手のバックエンド 1体につき +200（最大 +600 = 最大 1000） | Knowledge Graph |

### Trap（1枚）

| # | カード名 | 発動条件 | 効果 | 元ネタ |
|---|---------|---------|------|----------|
| 68 | Guruguru Error Budget | 自分の Guruguru Component が破壊される攻撃を受けた時 | AV 200 で生存（この Trap は破壊される） | SRE Error Budget |

---

## Miracle — 17枚

### Frontend（6枚）

| # | カード名 | タイプ | TP | AV | Request Cost | Deploy Cost | SLA Penalty | 効果 | 元ネタ |
|---|---------|-------|-----|-----|-----|-----|-----|------|----------|
| 70 | Miracle Compute | Compute (R) | 600 | 1500 | 100 | 300 | 400 | — | OCI Compute |
| 72 | Miracle Bare Metal | Compute (R) | 1300 | 1000 | 100 | 600 | 500 | **No Virtualization:** 攻撃時、このカードに 300 ダメージを与える | OCI Bare Metal |
| 73 | Miracle Container | Container (E) | 700→1300 | 1400 | 400 | 300 | 400 | — | OCI Container |
| 74 | Katastrophe | Orchestrator (R+E) | 600→1000 | 1600 | 100 | 600 | 500 | **Always Free:** small → medium の Scale Cost 0 | OKE |
| 75 | Miracle Functions | Serverless (E) | 500→900 | 1200 | 0 | 100 | 200 | — | OCI Functions |
| 76 | Miracle APEX | Serverless (E) | 300→600 | 1400 | 0 | 0 | 200 | **Low-Code:** Deploy Cost 0。場に Miracle DB があれば TP +400 | Oracle APEX |

### Back Line（4枚）

| # | カード名 | タイプ | DV | AV | Deploy Cost | SLA Penalty | 効果 | 元ネタ |
|---|---------|-------|-----|-----|-----|-----|------|----------|
| 77 | Miracle Autonomous | Database (E) | 500→700 | 1500 | 400 | 700 | — | Autonomous DB |
| 78 | Miracle Excelsis | Database (R) | 900 | 1200 | 800 | 1000 | — | Exadata Cloud |
| 79 | Miracle Storage | Storage | 200 | 1500 | 100 | 200 | — | OCI Object Storage |
| 81 | Miracle Cache | Cache DB (R) | 200 | 1300 | 200 | 300 | — | OCI Cache with Redis |

### Platform（3枚）

| # | カード名 | 種別 | 効果 | 元ネタ |
|---|---------|------|------|----------|
| 82 | Miracle DevOps | CI/CD | Miracle の Scale Up コスト -300（最低 0） | OCI DevOps |
| 83 | Miracle Guard | Security (Detect) | 相手の伏せ Trap 1枚を確認。場に Miracle カード 3枚以上で Incident ダメージ -200 | Cloud Guard |
| 84 | Miracle WAF | Security (Block) | DDoS Attack / Data Breach を無効化 | OCI WAF |

### Attachment（2枚）

| # | カード名 | 装備先 | 効果 | 元ネタ |
|---|---------|-------|------|----------|
| 85 | Miracle Data Guard | DB | **Standby:** 破壊時、リポジトリから Miracle DB を AV 200 で即デプロイ（Deploy Cost 0）。この効果は1ゲーム中に1回のみ使用できる | Oracle Data Guard |
| 86 | Miracle RAC | DB | **Real Application Clusters:** AV +400。Incident ダメージ -200 | Oracle RAC |

### Strategy（1枚）

| # | カード名 | Cost | 効果 | 元ネタ |
|---|---------|------|------|----------|
| 89 | Miracle License | 100 | Miracle の DB 1体の AV を全回復 | Oracle License |

### Trap（1枚）

| # | カード名 | 発動条件 | 効果 | 元ネタ |
|---|---------|---------|------|----------|
| 90 | Miracle Failback | 自分の Miracle DB が破壊された時 | 手札から Miracle DB 1枚を Deploy Cost 0 で即デプロイ | Data Guard Failback |

---

## Neutral — 29枚

### Attachment（6枚）

| # | カード名 | 装備先 | 効果 | 元ネタ |
|---|---------|-------|------|-------|
| 91 | Load Balancer | フロントエンド | **Traffic Distribution:** 場に他のフロントエンドが 1体以上いる限り、装備先は Battle Phase の攻撃対象に選択できない（Incident は対象可） | Load Balancer |
| 92 | Auto Scaler | Resizable フロントエンド | **Elastic Scaling:** Scale Up 時、TP に +300 追加 | Auto Scaling |
| 93 | Private IP | バックエンド | **Private Network:** Incident の対象にならない | VPC |
| 94 | Multi-AZ Deploy | Component | **高可用性:** AV +500 | Multi-AZ |
| 95 | Security Group | Component | **SG:** Incident ダメージ -200 | Security Group |
| 119 | DB Snapshot | DB | **Automated Backup:** 場に自分の Storage がある場合、装備先への攻撃ダメージ -400 | Automated Backup |

### Platform（2枚）

| # | カード名 | 種別 | 効果 | 元ネタ |
|---|---------|------|------|-------|
| 96 | ISMS Certification | Security (Cert) | Incident ダメージ全体 -200 | ISMS |
| 97 | SOC2 Certification | Security (Cert) | 自分の Component が破壊された時、SLA Penalty -100（最低 0） | SOC 2 |

### Strategy（7枚）

| # | カード名 | Cost | 効果 | 元ネタ |
|---|---------|------|------|-------|
| 98 | Cloud Engineer | 0 | 1枚ドロー。引いたカードが Miracle カードならトラッシュに送る | — |
| 99 | Cloud Architect | 0 | 2枚ドロー、1枚捨てる。引いた Miracle カードはトラッシュに送る | — |
| 100 | Terakoya | 200 | リポジトリから Component 1枚を手札に加える | Terraform |
| 101 | Budget Recovery | 0 | Budget +400 | — |
| 102 | Startup Funding | 0 | Budget +700。ただし相手も Budget +300 | — |
| 103 | Open Source Migration | 300 | 相手の Platform 1枚を破壊 | OSS Migration |
| 120 | Venture Capital Investment | 0 | Budget ≤ 1000 の時のみ使用可能。Budget +900 | — |

### Incident（9枚）

**1ターン1枚制限。Budget コストで使用。DV 奪取系は Security(Block) で軽減/無効化。**

| # | カード名 | Cost | 効果 | 元ネタ |
|---|---------|------|------|-------|
| 104 | DDoS Attack | 400 | 相手のフロントエンドから選択した1体に 900 ダメージを与える | DDoS |
| 105 | Data Breach | 600 | 相手のバックエンドから選択した1体に 600 ダメージを与え、相手の Budget を -300 する | Data Breach |
| 106 | Config Error | 200 | 相手のフロントエンドから選択した1体の TP を次ターン終了まで 0 にする | Misconfiguration |
| 107 | Data Scraping | 200 | 相手の DV を 600 奪う。相手のバックエンドが 0体なら不発 | Web Scraping |
| 108 | Crawler Bot | 0 | 相手の DV を 300 奪う。Security (Block) で無効化 | Bot Attack |
| 109 | Region Outage | 600 | 相手のバックエンド全体に 500 ダメージを与える | Region Outage |
| 110 | Crypto Mining | 200 | 相手のフロントエンドから選択した1体に 400 ダメージを与え、相手の Budget を -200 する | Cryptojacking |
| 111 | Ransomware | 800 | 相手の Component 1体を選択。次の相手ターン終了まで機能停止（DV Gen 0, TP 0, 攻撃不可） | Ransomware |
| 112 | Compliance Audit | 0 | 相手 Budget -400。Security Platform がなければ -900 | Compliance Audit |

### Trap（5枚）

| # | カード名 | 発動条件 | 効果 | 元ネタ |
|---|---------|---------|------|-------|
| 113 | Rate Limiter | 相手が Incident 使用時 | その Incident を無効化 | Rate Limiting |
| 114 | Auto Snapshot | 自分の Component 破壊時 | その SLA Penalty を 0 にする | Snapshot |
| 115 | Failover | 自分のフロントエンド破壊時 | 手札から同タイプを Deploy Cost 0 で即配置 | Failover |
| 116 | Circuit Breaker | 自分の Component が AV 0 以下になる攻撃を受けた時 | AV 200 で生存（この Trap は破壊される） | Circuit Breaker |
| 117 | Chaos Engineering | 相手が攻撃宣言した時 | その攻撃の対象を相手のフロントエンド 1体にリダイレクト（相手が対象を選ぶ） | Chaos Engineering |


---

## カード総数サマリ

| カテゴリ | SWS | Aozora | Guruguru | Miracle | Neutral | 合計 |
|---------|-----|--------|--------|-----|---------|------|
| Frontend | 5 | 6 | 7 | 6 | 0 | 24 |
| Backend | 6 | 5 | 6 | 4 | 0 | 21 |
| Platform | 4 | 4 | 3 | 3 | 2 | 16 |
| Attachment | 3 | 4 | 3 | 2 | 6 | 18 |
| Strategy | 5 | 3 | 3 | 1 | 7 | 19 |
| Incident | 0 | 0 | 0 | 0 | 9 | 9 |
| Trap | 1 | 4 | 1 | 1 | 5 | 12 |
| **合計** | **24** | **26** | **23** | **17** | **29** | **119** |
