# Unicorn Duel - Card List

**SPEC v0.14 対応**

## 凡例

- 数値は **tiny (Lv.1)** 基準。Scalable カードは `Base × 2^(Rank-1)` でスケール
- Instance Family (M系/C系/R系) 倍率は base 値に乗算（Compute: Throughput, Database: Generate に適用）
- **制限** = デッキ投入上限（記載なしは **3枚**）
- ★ = 提案値（バランス調整で変動する可能性あり）
- ☆ = 要検討（未確定）
- **太字効果名** = カード固有効果（遊戯王のモンスター効果に相当）
- T = Throughput, G = Generate, A = Availability, M = Maintenance

### 陣営コンセプト（スペック傾向）

| 陣営 | Throughput | Availability | Maintenance | Generate | 方向性 |
|------|-----------|-------------|-------------|---------|--------|
| **SWS** | 標準 | 標準 | 標準 | 標準 | 万能バランス。シナジーで勝つ |
| **Aozora** | やや低い | **高い** | 標準〜安い | やや低い | 堅牢・防御。耐えて勝つ |
| **Doodle** | **高い** | 低い | やや高い | やや高い | 高火力・脆い。短期決戦 |
| **MCI** | 低い | やや低い | 安い | **DB極高** | DB特化。堅実な収益基盤 |

---

## 1. Component Cards

### 1.1 Compute（Scalable）

Instance Family 選択可（カード効果で制限がある場合を除く）。Rep上限貢献: **×5**

| カード名 | 陣営 | T | A | M | 効果 | 制限 | 元サービス |
|---------|------|---|---|---|------|------|----------|
| Smile Compute | SWS | 150 | 100 | 30 | — （バランス型の王道） | 3 | Amazon EC2 |
| Smile Lite | SWS | 100 | 120 | 20 | **Easy Deploy:** デプロイコスト 0。C/R系不可（M系のみ） | 3 | Amazon Lightsail |
| Smile App Runner | SWS | 120 | 110 | 25 | **Auto Provision:** 場にContainer/Serverlessがあれば T +30% | 2 | AWS App Runner |
| Aozora Compute | Aozora | 140 | 110 | 30 | — （高耐久。Incident に強い） | 3 | Azure Virtual Machines |
| Aozora App Service | Aozora | 110 | 130 | 25 | **Managed Platform:** C系不可。Incidentダメージ -20% | 3 | Azure App Service |
| Aozora Spot | Aozora | 160 | 80 | 18 | **Preemptible:** ターン終了時1d6。1でTerminate。超低コスト | 3 | Azure Spot VM |
| Doodle Compute | Doodle | 165 | 90 | 32 | — （高スループット。攻撃的換金） | 3 | Google Compute Engine |
| Doodle App Engine | Doodle | 130 | 100 | 28 | **Managed Runtime:** C系不可。このターンの総変換500超でボーナス Credit +100 | 3 | Google App Engine |
| Doodle Preemptible | Doodle | 180 | 70 | 16 | **Spot Instance:** ターン終了時1d6。1-2でTerminate。最安の高T | 3 | Preemptible VM |
| Miracle Compute | MCI | 130 | 95 | 28 | — （低コスト低性能。DB の補助役） | 3 | OCI Compute |
| Miracle Ampere | MCI | 120 | 100 | 22 | **ARM Efficiency:** ゲーム最安Compute。場にMCI DB 2体以上で T +20% | 3 | OCI Ampere A1 |

> **Instance Family 適用例（Smile Compute, tiny）：**
> M系: T 150 / A 100 / M 30 | C系: T 225 / A 70 / M 36 | R系: T 105 / A 150 / M 36

---

### 1.2 Database（Scalable）

Instance Family 選択可（C系 → Generate×1.5, R系 → Generate×0.7）。蓄積上限: Generate × 3（効果で変動あり）

| カード名 | 陣営 | G | A | M | 効果 | 制限 | 元サービス |
|---------|------|---|---|---|------|------|----------|
| Smile Database | SWS | 200 | 80 | 35 | — （バランス型） | 3 | Amazon RDS |
| Smile Aurora | SWS | 210 | 90 | 40 | **Read Replica:** 場の他の活性DB 1体につき G +30% | 2 | Amazon Aurora |
| Aozora Database | Aozora | 190 | 100 | 36 | — （最も壊れにくい DB） | 3 | Azure SQL Database |
| Aozora Hyperscale | Aozora | 200 | 110 | 42 | **Elastic Pool:** 場の他のDBが破壊された時、G +50%（2ターン持続） | 2 | Azure SQL Hyperscale |
| Doodle SQL | Doodle | 190 | 70 | 33 | — （標準マネージドDB。手頃なコスト） | 3 | Cloud SQL |
| Doodle Spanner | Doodle | 300 | 55 | 68 | **Global Consistency:** IncidentでAが下がってもGは低下しない（常にフル生成）。蓄積上限 = G×4 | **1** | Cloud Spanner |
| Doodle AlloyDB | Doodle | 250 | 65 | 48 | **Columnar Engine:** このDBからData Valueを変換するComputeの変換効率 +20% | 2 | AlloyDB |
| **Miracle Database** | **MCI** | **300** | **120** | **52** | **基本スペック約1.5倍** | 3 | Oracle Autonomous DB |
| **Miracle Exadata** | **MCI** | **350** | **130** | **65** | **Exadata Processing:** ゲーム最高G (350)。Rank 3+で G +20%。蓄積上限 = G×4 | **1** | Exadata Cloud Service |
| Miracle HeatWave | MCI | 250 | 100 | 45 | **In-Memory Analytics:** 蓄積Data Value 100まで毎ターン自力Credit変換。f(Rep)適用 | 2 | MySQL HeatWave |

> MCI の DB は Generate 250-350 — 他陣営の約1.5倍。Starting Field で Miracle Database を配置すれば序盤から圧倒的な収益基盤。
> Doodle Spanner (G:300, M:68) は「Incidentを受けてもGenerate低下しない」唯一のDB — IncidentメタのDB。高性能だが高コスト。
> Doodle は Cloud SQL (G:190) → AlloyDB (G:250) → Spanner (G:300) と明確な性能差・コスト差の3段階ラインナップ。
> Smile Aurora の Read Replica は Multi-DB 構成で真価を発揮（DB 2体で +60%、有効G = 336）。

---

### 1.3 NoSQL（Fixed）— v0.12 新規

DB扱い（整合性チェックをパス）。ランクアップ不可。蓄積上限: Generate × 5。
Instance Family 不可。「対象: Scalable」の Incident を受けない。

| カード名 | 陣営 | G | A | M | 効果 | 制限 | 元サービス |
|---------|------|---|---|---|------|------|----------|
| Smile DynamoDB | SWS | 150 | 250 | 35 | **On-Demand:** 200 Credit支払いでこのターンG 2倍（1回/turn） | 3 | Amazon DynamoDB |
| Aozora Cosmos | Aozora | 140 | 280 | 40 | **Multi-Model:** Architecture ScoringではStorageとしてもカウント（3-Tier Webを単体で満たせる） | 2 | Azure Cosmos DB |
| Doodle Firestore | Doodle | 130 | 220 | 30 | **Realtime Sync:** Componentをデプロイする度にG 1回分のData Valueを即座に追加蓄積 | 3 | Cloud Firestore |
| Doodle Bigtable | Doodle | 180 | 180 | 50 | **Wide Column:** 蓄積上限 = G×8。データ蓄積戦略の要 | 2 | Cloud Bigtable |
| Miracle NoSQL | MCI | 160 | 240 | 35 | **Oracle Optimized:** 場にMiracle Databaseがあれば G +20% | 3 | OCI NoSQL Database |

> NoSQL は Fixed でIncident耐性が高いが、Generate の天井が RDB より低い。
> Aozora Cosmos は唯一「DB + Storage 両方カウント」— Architecture Scoring の柔軟性が極めて高い。
> Doodle Bigtable は蓄積上限 G×8 — 他の NoSQL (×5) や RDB (×3) を圧倒するバッファ。蓄積→一括変換コンボ用。

---

### 1.4 Storage（Fixed）

ランクアップ不可。蓄積上限なし（効果で制約がある場合を除く）。

| カード名 | 陣営 | G | A | M | 効果 | 制限 | 元サービス |
|---------|------|---|---|---|------|------|----------|
| Smile Storage | SWS | 50 | 250 | 蓄積×10% | — （標準） | 3 | Amazon S3 |
| Smile Glacier | SWS | 50 | 300 | 蓄積×3% | **Deep Archive:** Data Value生成後1ターン凍結（Compute取得不可）。超低M | 3 | S3 Glacier |
| Smile Warehouse | SWS | 80 | 200 | 蓄積×12% | **Analytics Engine:** 毎ターン蓄積Data Value 150まで自力Credit変換（Compute不要）。f(Rep)適用 | 2 | Amazon Redshift |
| Aozora Storage | Aozora | 45 | 300 | 蓄積×8% | — （超高耐久・低コスト） | 3 | Azure Blob Storage |
| Aozora Archive | Aozora | 40 | 350 | 蓄積×2% | **Cold Tier:** Data Value 2ターン凍結。ゲーム最安M。A 350（ほぼ破壊不可能） | 3 | Azure Archive Storage |
| Aozora Data Lake | Aozora | 60 | 250 | 蓄積×10% | **Hierarchical:** Data Lake アーキテクチャのStorage要件を **2体分** としてカウント | 2 | Azure Data Lake Storage |
| Doodle Storage | Doodle | 60 | 200 | 蓄積×12% | — （高Generate だがコスト高） | 3 | Google Cloud Storage |
| Doodle Archive | Doodle | 55 | 220 | 蓄積×4% | **Nearline:** Data Value 1ターン凍結。低コスト | 3 | GCS Nearline/Archive |
| **Doodle BigQuery** | **Doodle** | **100** | **180** | **蓄積×15%** | **Serverless Analytics:** 毎ターン蓄積Data Value 200まで自力Credit変換（Compute不要）。f(Rep)適用。ゲーム最高Storage G | **1** | BigQuery |
| Miracle Storage | MCI | 50 | 250 | 蓄積×10% | — （標準） | 3 | OCI Object Storage |
| Miracle Archive | MCI | 45 | 280 | 蓄積×5% | **Tiered Storage:** Data Value 1ターン凍結。凍結解除時G +10%（データ熟成） | 3 | OCI Archive Storage |

> **自己変換効果（DWH系）:** BigQuery (200/turn), Smile Warehouse (150/turn) は Compute なしでCredit変換可能。
> ただし変換量は Compute の Throughput (150-250) より低く抑えてあり、Compute を完全に代替はしない。
> **Archive系:** Maintenance が極めて安い（2-5%）代わりにデータの即時利用ができない。長期戦向け。

---

### 1.5 Serverless（Fixed）

ランクアップ不可。Rep上限貢献: **×8** ★

| カード名 | 陣営 | T | A | M | 効果 | 制限 | 元サービス |
|---------|------|---|---|---|------|------|----------|
| Smile Functions | SWS | 100 | 200 ★ | Credit×15% | — | 3 | AWS Lambda |
| Aozora Functions | Aozora | 90 | 220 ★ | Credit×12% | — （低コスト） | 3 | Azure Functions |
| Doodle Functions | Doodle | 120 | 180 ★ | Credit×18% | — （高スループット） | 3 | Cloud Functions |
| Miracle Functions | MCI | 90 | 200 ★ | Credit×13% | — | 3 | OCI Functions |
| Miracle APEX | MCI | 80 | 220 ★ | Credit×10% | **Low-Code:** デプロイコスト 0。場にMiracle Databaseがあれば T +50%。ゲーム最安Serverless | 2 | Oracle APEX |

> Miracle APEX は MCI 固有の Serverless — DB があれば T 120 相当。DB 陣営の安価なサブ換金手段。

---

### 1.6 Container（Fixed ★）

Rep上限貢献: **×15**

| カード名 | 陣営 | T | A | M | 効果 | 制限 | 元サービス |
|---------|------|---|---|---|------|------|----------|
| Smile Container | SWS | 250 | 150 | 55 | 場にOrchestratorもあれば T +20% | 2 | Amazon ECS / Fargate |
| Aozora Container | Aozora | 230 | 170 | 52 | **Quick Start:** デプロイコスト = M×1（通常の半額） | 2 | Azure Container Instances |
| Doodle Run | Doodle | 280 | 140 | 58 | **Scale to Zero:** 前ターンにこのカード経由の変換がなかった場合、M = 0 | 2 | Cloud Run |
| Miracle Container | MCI | 210 | 160 | 48 | **Lightweight Deploy:** デプロイコスト = M×1 | 2 | OCI Container Instances |

> Container は基本 Compute (T:130-180) を大幅に上回る Throughput (T:210-280) を持つ。
> Fixed なのでランクアップ不可だが、高い基本性能と Rep上限貢献 ×15 で即戦力。
> 高 Maintenance (M:48-58) がトレードオフ — Compute のスケーリング自由度を取るか、Container の即時パワーを取るか。

---

### 1.7 Orchestrator（Scalable）

ノードベースのスケールアウト。Instance Family 選択可。Rep上限貢献: **×25**。制限: **2枚** ★

| カード名 | 陣営 | T | A | M | 効果 | 制限 | 元サービス |
|---------|------|---|---|---|------|------|----------|
| Smile Kubernetes | SWS | 200 | 80 | 62 | — （バランス型） | 2 | Amazon EKS |
| Aozora Kubernetes | Aozora | 185 | 90 | 58 | — （高耐久） | 2 | Azure AKS |
| Doodle Kubernetes | Doodle | 220 | 75 | 68 | **Autopilot:** 1ゲーム1回、Main Phase開始時に2ランク無料スケールアップ | 2 | Google GKE |
| Miracle Kubernetes | MCI | 175 | 85 | 55 | **Always Free Tier:** tiny→micro のランクアップ後2ターンの間、追加M なし | 2 | Oracle OKE |

> Orchestrator は基本 Compute (T:130-180) を上回る Throughput (T:175-220) を持ち、さらにランクアップで指数的に成長。
> micro (T:350-440) → small (T:700-880) と、上位ランクでは圧倒的な変換力。
> Rep上限貢献 ×25 と合わせ、終盤の支配力は全Compute種別で最高。ただし Maintenance も最高クラス。

---

### 1.8 AI/ML Compute（Scalable）

Instance Family 選択可。Rep上限貢献: **×10** ★。制限: **2枚** ★。MCI は AI/ML カードなし。

| カード名 | 陣営 | T | A | M | 効果 | 制限 | 元サービス |
|---------|------|---|---|---|------|------|----------|
| Smile AI | SWS | 230 | 55 | 70 | — | 2 | Amazon SageMaker |
| Aozora AI | Aozora | 210 | 65 | 62 | — （AI 中では最も堅牢） | 2 | Azure Machine Learning |
| **Doodle AI** | **Doodle** | **270** | **45** | **78** | — （**最強の AI カード**） | 2 | Vertex AI |
| **Doodle TPU** | **Doodle** | **330** | **35** | **110** | **Tensor Processing:** ゲーム最高T (330)。破壊されたら場の全Data Valueの30%を消失 | **1** | Cloud TPU |

> AI/ML は全般的にハイリスク・ハイリターン。高 Throughput (T:210-330) だが Availability が極めて低い (A:35-65)。
> Doodle TPU (T:330) はゲーム中最高の Throughput を持つが、A:35 で即死級の脆さ。M:110 も全カード最高。
> 破壊時の場全体 Data Value -30% は壊滅的 — 守れなければ致命的なリスク。
> 投資対効果は抜群だが、Incident の的になりやすい。Security Platform との組み合わせが必須。

---

### 1.9 Cache DB（Scalable）

Instance Family 選択可。デプロイ時に **Rep × 1.3** の一時ブースト。蓄積上限: Generate × 2。制限: **2枚** ★

| カード名 | 陣営 | G | A | M | 効果 | 制限 | 元サービス |
|---------|------|---|---|---|------|------|----------|
| Smile Cache | SWS | 65 | 60 | 24 | — | 2 | Amazon ElastiCache |
| Aozora Cache | Aozora | 55 | 70 | 22 | **Geo-Replication:** Aozora CDNが場にあれば Rep×1.5 に強化（通常1.3） | 2 | Azure Cache for Redis |
| Doodle Cache | Doodle | 75 | 50 | 28 | — | 2 | Memorystore |
| Miracle Cache | MCI | 65 | 65 | 23 | **DB Accelerator:** 場のMiracle Database の G +15% | 2 | OCI Cache |

> Cache DB は v0.14 で Fixed → Scalable に変更。実際の ElastiCache / Memorystore がインスタンスタイプを選択できることを反映。
> ランクアップ + Instance Family 選択が可能になったが、「対象: Scalable」の Incident を受けるようになった。
> tiny 時の基本スペックは控えめだが、micro (G:130, A:120) → small (G:260, A:240) と成長。
> 蓄積上限 G×2 — キャッシュは揮発性データのため、DB (G×3) や NoSQL (G×5) より短いバッファ。

---

## 2. Platform Cards

最大3枚。自由に張り替え可能。Component / Attachment+Reactive とは独立枠。

### 2.1 DevOps 系（CI/CD）

Rep **+N%/turn**（具体倍率は調整中。10% 未満を想定）

| カード名 | 陣営 | 効果 | 備考 |
|---------|------|------|------|
| Smile Pipeline | SWS | Rep +N%/turn | CodePipeline |
| Aozora DevOps | Aozora | Rep +N%/turn | Azure DevOps |
| Doodle Build | Doodle | Rep +N%/turn | Cloud Build |
| Miracle Pipeline | MCI | Rep +N%/turn | OCI DevOps |

### 2.2 Network 系（CDN）

場にある限り **Rep × 1.5**。除去時に **Rep / 1.5**。

| カード名 | 陣営 | 効果 | 備考 |
|---------|------|------|------|
| Smile CDN | SWS | Rep ×1.5 (継続) | CloudFront |
| Aozora CDN | Aozora | Rep ×1.5 (継続) | Azure CDN |
| Doodle CDN | Doodle | Rep ×1.5 (継続) | Cloud CDN |

> MCI は CDN カードなし（Oracle CDN の存在感の薄さを反映）。MCI の戦略的弱点。

### 2.3 Network 系（DNS）— v0.12 新規

| カード名 | 陣営 | 効果 | 制限 | 備考 |
|---------|------|------|------|------|
| Smile DNS | SWS | **Health Routing:** ComponentのAが30%以下になった時、そのComponentのData Value生成を場の最も健全なComponentに1ターン移転 | 2 | Amazon Route 53 |

### 2.4 Security 系

#### 検知 (Detect)

| カード名 | 陣営 | 効果 | 備考 |
|---------|------|------|------|
| Smile Guard | SWS | Incident 使用前に内容を事前確認。Reactive 発動判断可 | GuardDuty |
| Smile Inspector | SWS | ターン開始時、相手の Incident 保持を確認 | Inspector |
| Aozora Sentinel | Aozora | Incident 使用前に内容を事前確認 + ダイスロール成功率 -1 ★ | Microsoft Sentinel |
| Aozora Defender | Aozora | **Threat Intel:** ターン開始時、相手のデッキトップ3枚を確認可能 | Microsoft Defender |
| Doodle Chronicle | Doodle | **Threat Analytics:** 相手がIncident使用時、100 Credit支払いで効果を50%軽減 | Chronicle Security |
| Miracle Guard | MCI | Incident事前確認。場にMCIカード3枚以上でダイスロール成功率 -1 | Cloud Guard |

#### 防御 (Block)

| カード名 | 陣営 | 効果 | 備考 |
|---------|------|------|------|
| Smile Firewall | SWS | Web 系 Incident を自動無効化 | AWS WAF |
| Smile Shield | SWS | DDoS Incident を自動無効化 | AWS Shield |
| Aozora Firewall | Aozora | Web 系 Incident を自動無効化 | Azure WAF |
| Aozora DDoS Guard | Aozora | DDoS Incident を自動無効化 | Azure DDoS Protection |
| Doodle Armor | Doodle | Web 系 Incident を自動無効化 | Cloud Armor |
| Miracle WAF | MCI | Web 系 Incident を自動無効化 | OCI WAF |

#### 認証 (Certification)

| カード名 | 陣営 | 効果 | 制限 | 備考 |
|---------|------|------|------|------|
| ISMS Certification | Neutral | 相手の全 Incident ダイスロール成功率 **-1** | 1枚 | ISMS認証 |
| SOC2 Certification | Neutral | ★ 効果検討中 | 1枚 ★ | SOC2認証 |
| Miracle Vault | MCI | **Master Encryption:** 場の全DBへのIncidentダメージ -10% | 2 | OCI Vault |

### 2.5 Utility 系 — v0.12 新規

| カード名 | 陣営 | 効果 | 制限 | 備考 |
|---------|------|------|------|------|
| Aozora Monitor | Aozora | **Observability:** Budget Approval時、A 50%以下のComponentがあれば Credit +100 | 3 | Azure Monitor |
| Doodle Monitoring | Doodle | **SLO Tracking:** 全Componentの A > 70% なら Rep +50/turn | 3 | Cloud Monitoring |
| Miracle Monitoring | MCI | **Always Free:** **Platform枠を消費しない。** ターン開始時、相手のIncident保持の有無を確認 | 2 | OCI Monitoring |

> Miracle Monitoring は Platform 枠を使わない — 実質的にPlatform 3枠 + Monitoring の4枚体制が可能。MCI のカード不足を補うユニーク効果。

---

## 3. Attachment Cards

Attachment + Reactive 合計で最大5枚。

### 3.1 汎用 Attachment（Neutral）

| カード名 | 効果 | 制限 | 備考 |
|---------|------|------|------|
| Auto Scaler | Compute装備。スケールアウト（性能×N倍★ / コスト緩やか増加）+ A 10%回復/turn | 3 | ASG |
| Load Balancer | A強化 + Rep上限貢献 ×2 + A 15%回復/turn | 3 | ELB/ALB |
| Private IP | DB装備。DB への直接 Incident を無効化（Compute 経由のみ被弾） | 3 | VPC Private Subnet |
| Security Group | 装備先への Incident ダメージを毎ターン1回無効化 | 3 | Security Group |
| Secret Vault | 装備先への Data Breach 系 Incident を無効化 ★ | 3 | Secrets Manager |
| Multi-AZ Deploy | A +20%。初めて破壊される時、代わりに A=1 で生存（このAttachment破壊） | 2 | Multi-AZ |
| Observability Stack | Compute装備。Budget Approval時、装備先 A > 80% なら1枚ドロー | 2 | 監視スタック |

### 3.2 SWS Attachment

| カード名 | 効果 | 制限 | 備考 |
|---------|------|------|------|
| Smile Identity | 装備先の Incident 耐性 UP ★ | 3 | IAM |
| Smile Queue | **Message Buffer:** Compute装備。T超過分のData Value 200まで次ターンに繰り越し | 3 | SQS |
| Smile Gateway | **API管理:** Compute/Serverless装備。T +15%。Serverless装備時は +25% | 2 | API Gateway |
| Smile EventBridge | **Event-Driven:** 場にComponentがデプロイ/破壊された時、1枚ドロー（1回/turn） | 2 | EventBridge |
| Smile StepFn | **Workflow:** Compute装備。Revenue Confirmで全Storage/DBから最適にData Valueを取得して変換 | 2 | Step Functions |
| Smile Notify | **Push通知:** 装備先がIncidentダメージを受けた時、手札からReactive1枚を即座に伏せ可能 | 3 | SNS |
| Smile KMS | **暗号化:** DB/Storage装備。Data Breach系Incident無効化。M +5 | 3 | KMS |

### 3.3 Aozora Attachment

| カード名 | 効果 | 制限 | 備考 |
|---------|------|------|------|
| Aozora Backup | 装備先が破壊された時、**1ターン後に A 50% で復元** ★ | 2 | Azure Backup |
| Aozora AD | 場の Aozora カード全体に Incident 耐性 +1 ★ | 2 | Azure Active Directory |
| Aozora Site Recovery | **DR:** 装備先が破壊された時、デッキからコピーをA 30%で即デプロイ。コスト不要。1ゲーム1回 | **1** | Azure Site Recovery |
| Aozora Logic Apps | **Automation:** Serverless/Container装備。Revenue Confirmで装備先のTをComputeのTに加算 | 2 | Logic Apps |
| Aozora Service Bus | **Reliable Messaging:** Compute装備。T超過分のData Valueを消失させず元のStorage/DBに残す | 2 | Service Bus |
| Aozora Key Vault | **Secret管理:** 装備先へのData Breach/Supply Chain Attack を無効化。M +8 | 2 | Key Vault |
| Aozora Event Grid | **Event React:** Platform装備。そのPlatformが破棄/張替えされる時、1回だけ無効化 | 2 | Event Grid |
| Aozora Private Link | **Private Link:** DB/Storage装備。Private IP と同等 + G +10% | 2 | Azure Private Link |

### 3.4 Doodle Attachment

| カード名 | 効果 | 制限 | 備考 |
|---------|------|------|------|
| Doodle Profiler | 装備先の T +20% ★ | 2 | Cloud Profiler |
| Doodle Pub/Sub | **Async Messaging:** Compute装備。T超過分の50%を次ターンに繰り越し変換 | 3 | Pub/Sub |
| Doodle Apigee | **API Monetization:** Compute/Serverless装備。Revenueに +10%ボーナス | 2 | Apigee |
| Doodle Dataflow | **Stream Processing:** Storage/DB装備。G +30%。装備先 M +20% | 2 | Dataflow |
| Doodle KMS | **CMEK:** DB/Storage装備。Data Breach無効化。M +5 | 3 | Cloud KMS |
| Doodle Eventarc | **Event Trigger:** Serverless装備。他のComponentがData Value生成するたびに追加50 Data Value変換 | 2 | Eventarc |

### 3.5 MCI Attachment

| カード名 | 効果 | 制限 | 備考 |
|---------|------|------|------|
| Miracle DB Guard | DB装備時、**G +20%** ★ | 2 | Oracle Data Guard |
| Miracle Data Guard | **Standby DB:** DB装備。破壊時デッキからコピーをA 40%で即デプロイ。コスト不要。1ゲーム1回 | **1** | OCI Data Guard |
| Miracle GoldenGate | **Data Replication:** DB装備。Data Generationで装備先DBが生成する際、場の全Storageにも +30 Data Value追加 | **1** | GoldenGate |
| Miracle RAC | **Real Application Clusters:** DB装備。A +30%。Incidentダメージ -20% | 2 | Oracle RAC |
| Miracle Queue | **Message Queue:** Compute装備。T超過 150まで次ターン繰り越し | 3 | OCI Queue |

---

## 4. Operation Cards

### 4.1 Strategy — IaC サーチ

すべて **制限カード（1枚）**。

| カード名 | 陣営 | 効果 | 備考 |
|---------|------|------|------|
| Smile Formation | SWS | デッキから **SWS** Component 1枚サーチ + **陣営バフ（★未定）** | CloudFormation |
| Aozora Template | Aozora | デッキから **Aozora** Component 1枚サーチ + **陣営バフ（★未定）** | ARM Templates |
| Doodle Deploy | Doodle | デッキから **Doodle** Component 1枚サーチ + **陣営バフ（★未定）** | Deployment Manager |
| Miracle Stack | MCI | デッキから **MCI** Component 1枚サーチ + **陣営バフ（★未定）** | OCI Resource Manager |
| **Terraform** | **Neutral** | デッキから **任意の** Component 1枚サーチ（バフなし） | Terraform (HashiCorp) |

### 4.2 Strategy — ドロー

| カード名 | 陣営 | 効果 | 制限 | 備考 |
|---------|------|------|------|------|
| Cloud Engineer | Neutral | デッキから **1枚ドロー** | 3 | 安定のドローソース |
| Cloud Architect | Neutral | デッキから **2枚ドロー、1枚捨てる** | **1** | 質の高いドロー |

### 4.3 Strategy — Platform サーチ

| カード名 | 陣営 | 効果 | 制限 | 備考 |
|---------|------|------|------|------|
| DevOps Engineer *(仮)* | Neutral | デッキから **Platform カード** 1枚サーチ | ★検討中 | CI/CD, CDN, Security を確保 |

### 4.4 Strategy — 陣営固有

| カード名 | 陣営 | 効果 | 制限 | 備考 |
|---------|------|------|------|------|
| Smile Marketplace | SWS | 場の SWS カードが 3種以上の時、**Credit +500** ★ | 3 | シナジーボーナス |
| Smile Well-Architected | SWS | **Review:** Architecture Scoring 3役以上発動中なら3枚ドロー。それ以外は1枚 | **1** | Well-Architected Framework |
| Smile Cost Explorer | SWS | **Cost分析:** このターンの全Maintenance 30%減 | 2 | Cost Explorer |
| Aozora Migration | Aozora | ゴミ箱から Aozora カード1枚を**手札に戻す** | 2 ★ | オンプレ→クラウド移行 |
| Aozora Hybrid | Aozora | **Hybrid Cloud:** ゴミ箱からComponent 1枚を手札に戻し、即座に半分のAでデプロイ可能（通常コスト要） | **1** | Azure Arc |
| Aozora Compliance | Aozora | **Governance:** このターン、相手は Incident カードを使用できない | **1** | Azure Policy |
| Doodle Analytics | Doodle | 場の Storage / DB の蓄積バリューを **一括変換**（T制限なし、1回限り） ★ | **1** | ビッグデータ爆発力 |
| Doodle Vertex Batch | Doodle | **AI Burst:** AI/ML or Compute 1体のTをこのターン2倍。次ターンそのカードは変換不可 | 2 | Vertex AI Batch |
| Doodle Data Studio | Doodle | **可視化:** 場にStorage/NoSQL 2体以上あれば、任意のソースから300 Data Valueを即座にCredit変換 | 2 | Looker |
| Miracle License | MCI | 場の Miracle Database の **M を1ターン 0 にする** ★ | 2 ★ | Oracle ライセンス割引 |
| Miracle Always Free | MCI | **Free Tier:** 手札から1枚をデプロイコスト 0 でデプロイ。3ターンの間 M 半額 | 2 | OCI Always Free |
| Miracle Autonomous | MCI | **Self-Driving DB:** Miracle Database 1体を選択。3ターンの間、毎ターン自動で1ランクアップ | **1** | Autonomous Operations |
| Miracle Consolidation | MCI | **統合:** 場のDB 2体以上ある時、1体をTerminate。残りのDB 1体の G +50%（永続）。Component枠を回収 | 2 | DB Consolidation |

### 4.5 Strategy — Neutral 汎用

| カード名 | 効果 | 制限 | 備考 |
|---------|------|------|------|
| SNS Buzz | **Rep +300** ★（固定値） | 3 | SNSバイラル |
| Budget Recovery | **Credit +1,500** ★ | 3 | 追加予算承認 |
| Startup Funding | Credit +1,000。Credit 5,000以下なら代わりに +2,000（逆転用） | 2 | VC資金調達 |
| Tech Conference | Rep +200。追加で手札を1枚捨てれば Rep +400 に強化 | 3 | re:Invent / Build 等 |
| Open Source Migration | 相手のPlatform 1枚を選び破壊する | **1** | OSS移行 |

### 4.6 Competition — 陣営固有（v0.13 新規）

**1ターン1枚制限**（Incident とは別枠）。効果は **経済的干渉のみ**（Availability には触れない）。
一部のカードに **逆転ボーナス**（自分の Rep < 相手の Rep で効果強化）。

#### SWS — エコシステム囲い込み

| カード名 | 効果 | 制限 | 備考 |
|---------|------|------|------|
| Smile Ecosystem Pressure | 場のSWSカード種類数 ≧ 相手のカード種類数 → 相手のこのターンの Revenue **-25%**。逆転ボーナス: **-40%** | 2 | AWS Marketplace 支配 |
| Smile Free Tier Blitz | 相手の Serverless/Container 1体を選択。このターンの T = 0（顧客が無料枠に流出） | 2 | AWS Free Tier |
| Smile Marketplace Takeover | 相手の Architecture Scoring 1役を選び無効化（このターン）。その役のボーナスの50%を自分が獲得 | **1** | Marketplace |

> SWS の「何でもある」強みで、相手のビジネスモデルを浸食する。

#### Aozora — エンタープライズ営業

| カード名 | 効果 | 制限 | 備考 |
|---------|------|------|------|
| Aozora Enterprise Deal | 相手の Rep を **150 奪取**（自分+150, 相手-150）。逆転ボーナス: **300 奪取** | 2 | EA契約切り替え |
| Aozora Bundle Strategy | 相手の次のターンのデプロイコスト **2倍** | 2 | Microsoft 365 バンドル |
| Aozora Compliance Pressure | 相手の Security Platform が1枚以下なら Rep **-200**。2枚以上なら無効 | 2 | コンプライアンス基準 |

> Microsoft の法人営業力で顧客を直接引き抜く。Rep 奪取は Aozora 固有の能力。

#### Doodle — 破壊的イノベーション

| カード名 | 効果 | 制限 | 備考 |
|---------|------|------|------|
| Doodle Open Source Release | 相手の Platform 1枚の効果を **2ターン無効化**（場に残るが効果なし） | 2 | Kubernetes/TF OSS化 |
| Doodle Talent Raid | 相手の Compute/AI 1体の T **-30%**（このターン）。自分の Compute/AI 1体の T **+30%** | 2 | Google 人材引き抜き |
| Doodle Data Democratization | 相手の場の蓄積 Data Value の **20% 消滅**。逆転ボーナス: **35%** | **1** | オープンデータ化 |

> Google の「技術で市場を再定義する」スタイル。相手の優位性そのものを無価値にする。

#### MCI — ライセンス圧力

| カード名 | 効果 | 制限 | 備考 |
|---------|------|------|------|
| Miracle License Audit | 相手の DB 全体の M をこのターン **+100%** | 2 | Oracle ライセンス監査 |
| Miracle Vendor Lock-in | 相手はこのターン Component の **Terminate（入れ替え）不可** | 2 | ベンダーロックイン |
| Miracle Price War | 自分の全 Component M **-20%**（このターン）、相手 **+10%**。逆転ボーナス: 自分-30%, 相手+20% | 2 | OCI 価格攻勢 |

> Oracle の「ライセンスで縛る」恐怖。DB を多く使う相手ほど刺さる。

#### Neutral — 市場変動

| カード名 | 効果 | 制限 | 備考 |
|---------|------|------|------|
| Startup Disruption | Rep が **高い方のプレイヤー** の Rep -10%。低い方は影響なし | 2 | スタートアップの破壊的参入 |
| Talent Shortage | 両プレイヤーの全 Compute T **-15%**（このターン）。Rep低い方は影響なし | 2 | エンジニア不足 |

> Neutral Competition は常にリーダー罰則 → デッキに入れるだけで逆転装置。

---

### 4.7 Incident

**1ターンに1枚まで。** ダメージは**現在 Availability ベース**。

#### 軽微（ダイスロールなし）

| カード名 | 対象 | 効果 | 制限 | 元ネタ |
|---------|------|------|------|--------|
| DDoS Attack | Scalable Compute 1体 | A **-30%** ★ | 3 | DDoS攻撃 |
| Config Error | Scalable 1体 | A **-20%** ★ + Credit **-200** ★ | 3 | S3公開設定ミス等 |
| Rate Limit Abuse | Serverless 1体 | そのターンの T **半減** ★ | 3 | API濫用 |
| Compliance Audit | プレイヤー | Credit -300。Security Platformがなければ -600 | 3 | SOC2/ISO監査 |

#### 中程度（ダイスロール: 1d6, 1〜2 で成功 = 33%）

| カード名 | 対象 | 効果 | 制限 | 元ネタ |
|---------|------|------|------|--------|
| Data Breach | DB 1体 | G 値ぶんの **Credit 損失** + Rep **-10%** ★ | 3 | 個人情報漏洩 |
| SQL Injection | DB 1体 | A **-40%** ★ | 3 | OWASP Top 10 |
| Supply Chain Attack | Component 1体 | A **-35%** ★ + Attachment 1枚破壊 ★ | 3 | SolarWinds事件 |
| Crypto Mining Attack | Compute 1体 | 対象のMをこのターン2倍。Credit -300 | 3 | クリプトジャッキング |

#### 重大（ダイスロール: 1d6, 1〜3 で成功 = 50%）

| カード名 | 対象 | 効果 | 制限 | 元ネタ |
|---------|------|------|------|--------|
| Zero-Day Exploit | Scalable 1体 | A **-60%** ★ + Rep **-15%** ★ | 3 | ゼロデイ脆弱性 |
| Regulatory Fine | プレイヤー | 前ターン収益の **50%** を Credit から徴収 ★ | 3 | GDPR制裁金 |
| Major Outage | Compute 全体 | 全 Compute の A **-25%** ★ | 3 | AWS/Azure大規模障害 |
| Region Outage | Storage 全体 | 全Storage A -20%。蓄積Data Value -10% | 2 | リージョン障害 |

#### 壊滅的（ダイスロール: 1d6, 1 のみ成功 = 17%）

| カード名 | 対象 | 効果 | 制限 | 元ネタ |
|---------|------|------|------|--------|
| Ransomware | DB or Compute 1体 | A **= 0**（即死） + Rep **-20%** ★ | **1** | ランサムウェア攻撃 |
| Class Action Lawsuit | Rep最高プレイヤー | 前ターン収益の **100%** を Credit から徴収 + Rep **-15%** ★ | **1** | 集団訴訟 |

---

## 5. Reactive Cards

裏向きで伏せ、条件で自動発動。Attachment + Reactive 合計5枚まで。最大チェーン深度: 2。

### 5.1 Neutral Reactive

| カード名 | 発動条件 | 効果 | 制限 | 元ネタ |
|---------|---------|------|------|--------|
| Auto Snapshot | 装備先が破壊された時 | 破壊された Component を **A 30% で復元** ★ | 3 | EBS Snapshot / Disk Snapshot |
| Rate Limiter | 相手が Incident を使用した時 | その Incident の効果を **半減** ★ | 3 | API Rate Limiting |
| Honeypot | 相手が DB を攻撃した時 | 攻撃を無効化し、相手の **Credit -500** ★ | 3 | ハニーポット |
| Failover | Compute が破壊された時 | 手札から Compute 1枚を **コスト0でデプロイ** ★ | 3 | Multi-AZ Failover |
| Circuit Breaker | Incidentで Component A < 20% | そのComponentへのそれ以上のダメージを無効化。A 20%で固定 | 2 | Circuit Breaker パターン |
| Chaos Engineering | 相手がIncident使用時 | そのIncidentの対象を**相手の場のComponentにリダイレクト** | **1** | Netflix Chaos Monkey |

### 5.2 陣営 Reactive

| カード名 | 陣営 | 発動条件 | 効果 | 制限 | 元サービス |
|---------|------|---------|------|------|----------|
| Smile Auto Heal | SWS | Compute A < 50% | A 70%まで回復 | 2 | EC2 Auto Recovery |
| Smile CloudWatch | SWS | Component A < 30% | そのComponentを1ランクダウン（M軽減）。tiny時効果なし | 2 | CloudWatch Alarm |
| Aozora Defender React | Aozora | 任意のIncident | **Incident完全無効化** | **1** | Microsoft Defender |
| Aozora Auto-Failover | Aozora | Compute破壊時 | 手札からCompute 1枚をコスト0でデプロイ。A 50%開始 | 2 | Azure Traffic Manager |
| Doodle Canary | Doodle | 相手がIncident保持（ターン開始時） | 相手の手札1枚公開 | 2 | Cloud Canary |
| Doodle Error Budget | Doodle | Incidentダメージ | Aが20%以下になるダメージの場合、代わりに20%で止まる（1撃破壊防止） | 2 | SRE Error Budget |
| Miracle Failback | MCI | DB破壊時 | 手札からDB 1枚をA 50%、コスト0で即デプロイ | 2 | Data Guard Failback |
| Miracle Patch | MCI | DBへのIncident | そのDBへのIncident効果を50%軽減 | 2 | Autonomous Patching |

---

## 6. カード総数サマリ

### 陣営別カード数

| カテゴリ | SWS | Aozora | Doodle | MCI | Neutral | 合計 |
|---------|-----|--------|--------|-----|---------|------|
| Compute | 3 | 3 | 3 | 2 | — | 11 |
| Database | 2 | 2 | 3 | 3 | — | 10 |
| NoSQL | 1 | 1 | 2 | 1 | — | 5 |
| Storage | 3 | 3 | 3 | 2 | — | 11 |
| Serverless | 1 | 1 | 1 | 2 | — | 5 |
| Container | 1 | 1 | 1 | 1 | — | 4 |
| Orchestrator | 1 | 1 | 1 | 1 | — | 4 |
| AI/ML | 1 | 1 | 2 | — | — | 4 |
| Cache DB | 1 | 1 | 1 | 1 | — | 4 |
| **Component 小計** | **14** | **14** | **17** | **13** | **0** | **58** |
| Platform | 7 | 7 | 5 | 5 | 2 | 26 |
| Attachment | 7 | 8 | 6 | 5 | 7 | 33 |
| Strategy | 4 | 4 | 4 | 5 | 10 | 27 |
| **Competition** | **3** | **3** | **3** | **3** | **2** | **14** |
| Incident | — | — | — | — | 13 | 13 |
| Reactive | 2 | 2 | 2 | 2 | 6 | 14 |
| **非Component 小計** | **23** | **24** | **20** | **20** | **40** | **127** |
| **陣営合計** | **37** | **38** | **37** | **33** | **40** | **185** |

> **デッキ構築:** 陣営カード (33〜38種) + Neutral (40種) から 20〜30枚を構成。
> v0.13 で Competition カード14枚を追加（合計185枚）。陣営固有の市場競争が新たなインタラクション軸に。
> MCI は意図的にカード数が少ない（OCI のサービスラインナップを反映）。DB の質で勝負する。

### 陣営ごとの独占/不在カード

| 陣営 | 独占カード | 不在カード |
|------|----------|----------|
| **SWS** | Smile DNS (Route53) | — （最も幅広いカタログ） |
| **Aozora** | Aozora Site Recovery, Aozora Cosmos (Multi-Model) | — |
| **Doodle** | Doodle BigQuery, Doodle TPU, Doodle Bigtable | — |
| **MCI** | Miracle Exadata, Miracle HeatWave, Miracle APEX, Miracle GoldenGate | CDN, AI/ML, DNS |

---

## 7. デッキ構築例

### SWS バランスシナジー型（25枚）

| 枚数 | カード名 | 役割 |
|------|---------|------|
| 2 | Smile Compute | メイン変換エンジン |
| 1 | Smile Aurora | Read Replica で G 強化 |
| 1 | Smile Database | サブ DB |
| 1 | Smile DynamoDB | NoSQL — Multi-DB Resilience |
| 2 | Smile Storage | Data Lake / 3-Tier Web |
| 1 | Smile Functions | サブ変換 |
| 1 | Smile Pipeline | CI/CD |
| 1 | Smile CDN | Rep ×1.5 |
| 1 | Smile Firewall | Web 系防御 |
| 1 | Smile Formation | IaC サーチ |
| 1 | Smile Marketplace | シナジーボーナス |
| 1 | Smile Well-Architected | 条件付き大量ドロー |
| 2 | Cloud Engineer | ドロー |
| 1 | Cloud Architect | 質ドロー |
| 1 | Terraform | 万能サーチ |
| 1 | Private IP | DB 保護 |
| 1 | Load Balancer | A + Rep上限 |
| 1 | Smile Queue | SQS — Message Buffer |
| 1 | Smile KMS | 暗号化 — Zero Trust |
| 1 | DDoS Attack | 軽微 Incident |
| 1 | Smile Ecosystem Pressure | **Competition — Revenue 妨害** |
| 1 | Auto Snapshot | 防御 Reactive |
| 1 | Smile EventBridge | Event-Driven ドロー |

> 狙える Architecture: 3-Tier Web (+100) + DevOps Ready (+100) + Multi-DB (+100) + Hybrid Data (+110) + Event-Driven (+130) = **+540/turn**
> Competition: SWS の豊富なカード種類を活かして相手の Revenue を削る。

### MCI DB 要塞型（22枚）

| 枚数 | カード名 | 役割 |
|------|---------|------|
| 2 | Miracle Compute | 変換エンジン |
| 1 | Miracle Ampere | 低コスト変換 |
| 2 | Miracle Database | **主力。** 圧倒的 Generate |
| 1 | Miracle Exadata | **究極DB。** G 350 |
| 1 | Miracle NoSQL | Oracle Optimized で G +20% |
| 1 | Miracle Storage | 3-Tier Web 用 |
| 1 | Miracle APEX | DB連携の低コスト Serverless |
| 1 | Miracle Pipeline | CI/CD |
| 1 | Miracle Stack | IaC サーチ |
| 1 | Miracle License | DB Maintenance 軽減 |
| 1 | Miracle Autonomous | Self-Driving DB で自動ランクアップ |
| 2 | Cloud Engineer | ドロー |
| 1 | Terraform | 万能サーチ |
| 2 | Private IP | DB 保護 |
| 1 | Miracle RAC | DB 強化 + 防御 |
| 1 | Miracle Data Guard | DB 破壊時の保険 |
| 1 | DDoS Attack | Incident |
| 1 | Miracle License Audit | **Competition — 相手DB コスト圧迫** |
| 1 | Miracle Failback | DB 破壊時の即復旧 |

> Starting Field: Miracle Exadata + Miracle Compute → 序盤から G 350 でデータ蓄積。
> 狙える Architecture: 3-Tier Web (+100) + DevOps Ready (+100) + Multi-DB (+100) + Hybrid Data (+110) = **+410/turn**
> Competition: License Audit で相手のDB Maintenance を倍増させ、資金を圧迫する。

### Doodle AI爆発型（25枚）

| 枚数 | カード名 | 役割 |
|------|---------|------|
| 2 | Doodle Compute | 高速変換 |
| 2 | Doodle SQL | 高 Generate DB |
| 1 | Doodle Spanner | Incident耐性DB |
| 1 | Doodle Firestore | Realtime Sync NoSQL |
| 1 | Doodle BigQuery | **自己変換Storage** |
| 1 | Doodle Storage | Data Lake 用 |
| 2 | Doodle AI | **Vertex AI。** T:200 の爆発力 |
| 1 | Doodle TPU | **切り札。** T:250 のガラスの大砲 |
| 1 | Doodle Build | CI/CD |
| 1 | Doodle CDN | Rep ×1.5 |
| 1 | Doodle Deploy | IaC サーチ |
| 1 | Doodle Analytics | **一括換金** |
| 1 | Doodle Vertex Batch | AI Burst |
| 2 | Cloud Engineer | ドロー |
| 1 | Terraform | 万能サーチ |
| 1 | Private IP | DB 保護 |
| 1 | Load Balancer | Rep 上限 |
| 1 | Doodle Pub/Sub | Async Messaging |
| 1 | Doodle Error Budget | 1撃破壊防止 |
| 1 | Doodle Open Source Release | **Competition — Platform 無効化** |
| 1 | Zero-Day Exploit | 重大 Incident |

> CDN + AI で Rep とThroughput を同時に爆発させる。BigQuery の自己変換で Compute に依存しない副収入も確保。
> 狙える Architecture: 3-Tier Web (+100) + DevOps Ready (+100) + AI/ML Pipeline (+150) + Hybrid Data (+110) = **+460/turn**
> Competition: 相手の CDN や CI/CD を 2ターン無効化して成長を止める。

### Aozora 鉄壁防御型（26枚）

| 枚数 | カード名 | 役割 |
|------|---------|------|
| 2 | Aozora Compute | メイン変換 |
| 1 | Aozora App Service | 低コスト + Incident -20% |
| 2 | Aozora Database | 堅牢 DB |
| 1 | Aozora Cosmos | **Multi-Model NoSQL** |
| 2 | Aozora Storage | 超高耐久 Storage |
| 1 | Aozora Functions | サブ変換 |
| 1 | Aozora DevOps | CI/CD |
| 1 | Aozora CDN | Rep ×1.5 |
| 1 | Aozora Sentinel | Detect + dice -1 |
| 1 | Aozora Firewall | Web系防御 |
| 1 | Aozora DDoS Guard | DDoS防御 |
| 1 | Aozora Template | IaC サーチ |
| 1 | Aozora Migration | ゴミ箱回収 |
| 1 | Aozora Compliance | **Incident封じ** |
| 2 | Cloud Engineer | ドロー |
| 1 | Terraform | 万能サーチ |
| 1 | Aozora Backup | 破壊時復元 |
| 1 | Aozora Site Recovery | **究極の保険** |
| 1 | Aozora Key Vault | Data Breach無効化 |
| 1 | Load Balancer | A + Rep上限 |
| 1 | Private IP | DB 保護 |
| 1 | Aozora Enterprise Deal | **Competition — Rep 奪取** |
| 1 | Aozora Defender React | **Incident完全無効化** |

> 3重の防御層: Security Platform (Sentinel+Firewall+DDoS) + Attachment (Backup+Site Recovery+Key Vault) + Reactive (Defender React)。
> 狙える Architecture: 3-Tier Web (+100) + DevOps Ready (+100) + Security Hardened (+80) + Zero Trust (+120) + Multi-DB (+100) + Hybrid Data (+110) = **+610/turn**
> Competition: Enterprise Deal で相手から Rep を直接奪取。逆転ボーナスで最大 300 奪取。
