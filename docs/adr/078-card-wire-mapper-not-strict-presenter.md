# ADR-078: domain と wire DTO の変換層は厳密な Presenter パターンでなく mapper として実装する

## ステータス

Accepted (2026-08-11)

## 結論

domain と wire DTO の境界変換を担う層は、クリーンアーキテクチャが定義する厳密な Presenter パターン (usecase が output port 経由で結果を押し出す構造) ではなく、usecase が変換関数を直接呼んで wire DTO を戻り値で返す mapper として実装する。usecase 層が wire DTO 型への依存を持つことを許容する。

## 背景・課題

厳密な Presenter パターンは、endpoint ごとに output port のインターフェースと Presenter の実装を用意する必要がある。対応する wire 形式が REST のみで、複数 wire 形式への差し替え要件が現状無いため、そのコストに見合わない。

Go は関数の戻り値で結果を返すスタイルを慣用とし、output port を介して副作用的に結果を押し出す構造とは相性がよくない。

変換ロジックを usecase / handler / repository から物理的に分離するという目的自体は、厳密な Presenter パターンを採らなくても mapper として達成できる。

## 不採用案

### 厳密な Presenter パターン (output port + wire 形式ごとの Presenter 実装) を採用する

却下。wire 形式が REST 単一で差し替え要件がない現状の規模に対し、endpoint ごとに output port とその実装を用意するコストが見合わない。
