// go-test-report は go test -json の出力ストリームを読み、
// $GITHUB_STEP_SUMMARY への表形式サマリと、失敗テストに対する
// GitHub Actions の workflow コマンド (::error::) を出力する。
package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"path"
	"regexp"
	"strconv"
	"strings"
)

// go test -json は、コンパイル失敗を通常のテストイベントとは別の
// スキーマ (Package の代わりに ImportPath、Action は build-output /
// build-fail) でも出力する。両方を同じ struct で受ける。
type testEvent struct {
	Action     string `json:"Action"`
	Package    string `json:"Package"`
	ImportPath string `json:"ImportPath"`
	Test       string `json:"Test"`
	Output     string `json:"Output"`
}

func (ev testEvent) buildPackage() string {
	if ev.ImportPath == "" {
		return ""
	}
	if i := strings.Index(ev.ImportPath, " ["); i >= 0 {
		return ev.ImportPath[:i]
	}
	return ev.ImportPath
}

type testResult struct {
	Package string
	Test    string
	Status  string
	Output  strings.Builder
}

type failure struct {
	name string
	file string
	line int
	msg  string
}

var fileLineRe = regexp.MustCompile(`(?m)^\s*([A-Za-z0-9_./-]+\.go):(\d+):(?:\d+:)?`)

func main() {
	if len(os.Args) < 3 {
		fmt.Fprintln(os.Stderr, "usage: go-test-report <json-path> <title>")
		os.Exit(1)
	}
	jsonPath := os.Args[1]
	title := os.Args[2]

	modulePath, err := readModulePath(os.Getenv("GITHUB_WORKSPACE"))
	if err != nil {
		fmt.Fprintf(os.Stderr, "go-test-report: module path 特定に失敗、file annotation は best-effort になる: %v\n", err)
	}

	f, err := os.Open(jsonPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "go-test-report: failed to open %s: %v\n", jsonPath, err)
		os.Exit(1)
	}
	defer f.Close()

	results := map[string]*testResult{}
	var order []string
	pkgHasTests := map[string]bool{}
	pkgOutput := map[string]*strings.Builder{}
	pkgFailed := map[string]bool{}
	var pkgOrder []string

	scanner := bufio.NewScanner(f)
	scanner.Buffer(make([]byte, 64*1024), 10*1024*1024)
	for scanner.Scan() {
		line := scanner.Bytes()
		if len(bytes.TrimSpace(line)) == 0 {
			continue
		}
		var ev testEvent
		if err := json.Unmarshal(line, &ev); err != nil {
			continue
		}

		if ev.Action == "build-output" || ev.Action == "build-fail" {
			pkg := ev.buildPackage()
			if pkg == "" {
				continue
			}
			if _, ok := pkgOutput[pkg]; !ok {
				pkgOutput[pkg] = &strings.Builder{}
				pkgOrder = append(pkgOrder, pkg)
			}
			if ev.Action == "build-output" {
				pkgOutput[pkg].WriteString(ev.Output)
			} else {
				pkgFailed[pkg] = true
			}
			continue
		}

		if ev.Test == "" {
			if _, ok := pkgOutput[ev.Package]; !ok {
				pkgOutput[ev.Package] = &strings.Builder{}
				pkgOrder = append(pkgOrder, ev.Package)
			}
			if ev.Action == "output" {
				pkgOutput[ev.Package].WriteString(ev.Output)
			}
			if ev.Action == "fail" {
				pkgFailed[ev.Package] = true
			}
			continue
		}

		pkgHasTests[ev.Package] = true
		key := ev.Package + "\x00" + ev.Test
		r, ok := results[key]
		if !ok {
			r = &testResult{Package: ev.Package, Test: ev.Test}
			results[key] = r
			order = append(order, key)
		}
		switch ev.Action {
		case "output":
			r.Output.WriteString(ev.Output)
		case "pass", "fail", "skip":
			r.Status = ev.Action
		default:
		}
	}
	if err := scanner.Err(); err != nil {
		fmt.Fprintf(os.Stderr, "go-test-report: failed to read %s: %v\n", jsonPath, err)
		os.Exit(1)
	}

	leaf := leafKeys(order, results)

	var passed, failed, skipped int
	var failures []failure
	for _, key := range order {
		if !leaf[key] {
			continue
		}
		r := results[key]
		switch r.Status {
		case "pass":
			passed++
		case "skip":
			skipped++
		case "fail":
			failed++
			file, line, msg := extractLocation(r.Output.String(), modulePath, r.Package)
			failures = append(failures, failure{name: r.Package + "." + r.Test, file: file, line: line, msg: msg})
		default:
		}
	}

	var buildFailures []failure
	for _, pkg := range pkgOrder {
		if pkgFailed[pkg] && !pkgHasTests[pkg] {
			file, line, msg := extractBuildFailureLocation(pkgOutput[pkg].String())
			buildFailures = append(buildFailures, failure{name: pkg + " (ビルド失敗)", file: file, line: line, msg: msg})
		}
	}

	writeSummary(title, passed, failed, skipped, failures, buildFailures)
	writeAnnotations(failures, buildFailures)
}

func readModulePath(workspace string) (string, error) {
	if workspace == "" {
		return "", fmt.Errorf("GITHUB_WORKSPACE is empty")
	}
	data, err := os.ReadFile(path.Join(workspace, "go.mod"))
	if err != nil {
		return "", err
	}
	for _, line := range strings.Split(string(data), "\n") {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, "module ") {
			return strings.TrimSpace(strings.TrimPrefix(line, "module")), nil
		}
	}
	return "", fmt.Errorf("module directive not found in go.mod")
}

// leafKeys は t.Run のネストで親テストにあたる結果を除く。親は子の
// pass/fail をそのまま集約した重複エントリで、file:line も持たないため
// 件数・annotation の対象は子 (葉) だけにする。
func leafKeys(order []string, results map[string]*testResult) map[string]bool {
	leaf := make(map[string]bool, len(order))
	for _, key := range order {
		leaf[key] = true
	}
	for _, key := range order {
		r := results[key]
		for _, otherKey := range order {
			if otherKey == key {
				continue
			}
			other := results[otherKey]
			if other.Package == r.Package && strings.HasPrefix(other.Test, r.Test+"/") {
				leaf[key] = false
				break
			}
		}
	}
	return leaf
}

// firstLocation は t.Errorf/t.Fatalf 等が出力する "file.go:line:" 形式の
// 最初の出現を探す。testing パッケージはファイル名を basename でしか
// 出力しないため、呼び出し側でパッケージのディレクトリと合成する。
func firstLocation(output string) (file string, line int, msg string, ok bool) {
	loc := fileLineRe.FindStringSubmatchIndex(output)
	if loc == nil {
		return "", 0, firstNonEmptyLine(output), false
	}
	file = output[loc[2]:loc[3]]
	line, _ = strconv.Atoi(output[loc[4]:loc[5]])
	rest := output[loc[1]:]
	if nl := strings.IndexByte(rest, '\n'); nl >= 0 {
		rest = rest[:nl]
	}
	msg = strings.TrimSpace(rest)
	if msg == "" {
		msg = file + " failed"
	}
	return file, line, msg, true
}

func extractLocation(output, modulePath, pkg string) (file string, line int, msg string) {
	base, ln, m, ok := firstLocation(output)
	if !ok {
		return "", 0, m
	}
	relDir := ""
	if modulePath != "" {
		if strings.HasPrefix(pkg, modulePath+"/") {
			relDir = strings.TrimPrefix(pkg, modulePath+"/")
		}
	}
	if relDir != "" {
		return path.Join(relDir, base), ln, m
	}
	return base, ln, m
}

// extractBuildFailureLocation はコンパイルエラーを扱う。go test はコンパイル
// エラーをカレントディレクトリ (リポジトリルート) からの相対パスで出力するため、
// テスト関数の失敗と異なりディレクトリ合成が不要。
func extractBuildFailureLocation(output string) (file string, line int, msg string) {
	base, ln, m, ok := firstLocation(output)
	if !ok {
		return "", 0, m
	}
	return strings.TrimPrefix(base, "./"), ln, m
}

func firstNonEmptyLine(s string) string {
	for _, line := range strings.Split(s, "\n") {
		line = strings.TrimSpace(line)
		if line != "" {
			return line
		}
	}
	return ""
}

func writeSummary(title string, passed, failed, skipped int, failures, buildFailures []failure) {
	summaryPath := os.Getenv("GITHUB_STEP_SUMMARY")
	if summaryPath == "" {
		return
	}
	f, err := os.OpenFile(summaryPath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		fmt.Fprintf(os.Stderr, "go-test-report: failed to open step summary: %v\n", err)
		return
	}
	defer f.Close()

	var b strings.Builder
	fmt.Fprintf(&b, "## %s\n\n", title)
	fmt.Fprintf(&b, "| 項目 | 件数 |\n|---|---|\n")
	fmt.Fprintf(&b, "| 通過 | %d |\n", passed)
	fmt.Fprintf(&b, "| 失敗 | %d |\n", failed+len(buildFailures))
	fmt.Fprintf(&b, "| スキップ | %d |\n", skipped)
	if failed > 0 || len(buildFailures) > 0 {
		fmt.Fprintf(&b, "\n失敗したテスト:\n\n")
		for _, bf := range buildFailures {
			fmt.Fprintf(&b, "- %s: %s\n", bf.name, bf.msg)
		}
		for _, ft := range failures {
			fmt.Fprintf(&b, "- %s\n", ft.name)
		}
	}
	b.WriteString("\n")
	f.WriteString(b.String())
}

func writeAnnotations(failures, buildFailures []failure) {
	for _, bf := range buildFailures {
		emitError(bf.file, bf.line, fmt.Sprintf("%s: %s", bf.name, bf.msg))
	}
	for _, ft := range failures {
		emitError(ft.file, ft.line, fmt.Sprintf("%s: %s", ft.name, ft.msg))
	}
}

func emitError(file string, line int, message string) {
	message = escapeData(message)
	if file != "" && line > 0 {
		fmt.Printf("::error file=%s,line=%d::%s\n", escapeProperty(file), line, message)
		return
	}
	fmt.Printf("::error::%s\n", message)
}

func escapeData(s string) string {
	s = strings.ReplaceAll(s, "%", "%25")
	s = strings.ReplaceAll(s, "\r", "%0D")
	s = strings.ReplaceAll(s, "\n", "%0A")
	return s
}

func escapeProperty(s string) string {
	s = escapeData(s)
	s = strings.ReplaceAll(s, ":", "%3A")
	s = strings.ReplaceAll(s, ",", "%2C")
	return s
}
