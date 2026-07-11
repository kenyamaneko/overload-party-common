package main

import (
	"os"
	"path"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestPrefixFile(t *testing.T) {
	t.Run("module-dir によるファイルパスの補正", func(t *testing.T) {
		cases := []struct {
			name         string
			modulePrefix string
			file         string
			wantFile     string
		}{
			{
				name:         "module-dir がリポジトリルート直下のとき、file はそのままになる",
				modulePrefix: "",
				file:         "internal/service/shipping_test.go",
				wantFile:     "internal/service/shipping_test.go",
			},
			{
				name:         "module-dir がサブディレクトリのとき、file の先頭に付与される",
				modulePrefix: "export-function",
				file:         "internal/service/shipping_test.go",
				wantFile:     "export-function/internal/service/shipping_test.go",
			},
			{
				name:         "file が空 (位置未特定) のとき、module-dir を付与しても空のままになる",
				modulePrefix: "export-function",
				file:         "",
				wantFile:     "",
			},
		}

		for _, tc := range cases {
			t.Run(tc.name, func(t *testing.T) {
				assert.Equal(t, tc.wantFile, prefixFile(tc.modulePrefix, tc.file))
			})
		}
	})
}

func TestLeafKeys(t *testing.T) {
	t.Run("t.Run ネストにおける葉テストの判定", func(t *testing.T) {
		t.Run("子テストが無いとき、そのテストは葉として扱われる", func(t *testing.T) {
			order := []string{"pkg\x00TestFoo"}
			results := map[string]*testResult{
				"pkg\x00TestFoo": {Package: "pkg", Test: "TestFoo"},
			}

			got := leafKeys(order, results)

			assert.True(t, got["pkg\x00TestFoo"])
		})

		t.Run("子テストがあるとき、親テストは葉として扱われない", func(t *testing.T) {
			order := []string{"pkg\x00TestFoo", "pkg\x00TestFoo/ケースA"}
			results := map[string]*testResult{
				"pkg\x00TestFoo":      {Package: "pkg", Test: "TestFoo"},
				"pkg\x00TestFoo/ケースA": {Package: "pkg", Test: "TestFoo/ケースA"},
			}

			got := leafKeys(order, results)

			assert.False(t, got["pkg\x00TestFoo"])
			assert.True(t, got["pkg\x00TestFoo/ケースA"])
		})

		t.Run("別パッケージに同名テストがあっても親子と誤判定しない", func(t *testing.T) {
			order := []string{"pkgA\x00TestFoo", "pkgB\x00TestFoo/ケースA"}
			results := map[string]*testResult{
				"pkgA\x00TestFoo":      {Package: "pkgA", Test: "TestFoo"},
				"pkgB\x00TestFoo/ケースA": {Package: "pkgB", Test: "TestFoo/ケースA"},
			}

			got := leafKeys(order, results)

			assert.True(t, got["pkgA\x00TestFoo"])
			assert.True(t, got["pkgB\x00TestFoo/ケースA"])
		})
	})
}

func TestExtractLocation(t *testing.T) {
	t.Run("テスト失敗箇所の抽出", func(t *testing.T) {
		cases := []struct {
			name       string
			output     string
			modulePath string
			pkg        string
			wantFile   string
			wantLine   int
			wantMsg    string
		}{
			{
				name:       "モジュールルート直下のパッケージで file:line が見つかったとき、ディレクトリ無しのファイルパスになる",
				output:     "    root_test.go:12: 期待値と異なる\n",
				modulePath: "github.com/kenyamaneko/example",
				pkg:        "github.com/kenyamaneko/example",
				wantFile:   "root_test.go",
				wantLine:   12,
				wantMsg:    "期待値と異なる",
			},
			{
				name:       "サブディレクトリのパッケージで file:line が見つかったとき、パッケージ相対ディレクトリを含むファイルパスになる",
				output:     "    shipping_test.go:34: 送料が一致しない",
				modulePath: "github.com/kenyamaneko/example",
				pkg:        "github.com/kenyamaneko/example/internal/service",
				wantFile:   "internal/service/shipping_test.go",
				wantLine:   34,
				wantMsg:    "送料が一致しない",
			},
			{
				name:       "file:line が見つからないとき、file は空文字になり最初の非空行がメッセージになる",
				output:     "\n  panic: 想定外の nil 参照\n\ngoroutine 1 [running]:\n",
				modulePath: "github.com/kenyamaneko/example",
				pkg:        "github.com/kenyamaneko/example/internal/service",
				wantFile:   "",
				wantLine:   0,
				wantMsg:    "panic: 想定外の nil 参照",
			},
		}

		for _, tc := range cases {
			t.Run(tc.name, func(t *testing.T) {
				file, line, msg := extractLocation(tc.output, tc.modulePath, tc.pkg)

				assert.Equal(t, tc.wantFile, file)
				assert.Equal(t, tc.wantLine, line)
				assert.Equal(t, tc.wantMsg, msg)
			})
		}
	})
}

func TestExtractBuildFailureLocation(t *testing.T) {
	t.Run("ビルド失敗箇所の抽出", func(t *testing.T) {
		cases := []struct {
			name     string
			output   string
			wantFile string
			wantLine int
			wantMsg  string
		}{
			{
				name:     "./ 接頭辞付きのパスのとき、接頭辞が取り除かれる",
				output:   "# github.com/kenyamaneko/example/internal/service\n./internal/service/shipping.go:10:2: undefined: Foo\n",
				wantFile: "internal/service/shipping.go",
				wantLine: 10,
				wantMsg:  "undefined: Foo",
			},
			{
				name:     "file:line が見つからないとき、file は空文字になり最初の非空行がメッセージになる",
				output:   "\nunexpected EOF\n",
				wantFile: "",
				wantLine: 0,
				wantMsg:  "unexpected EOF",
			},
		}

		for _, tc := range cases {
			t.Run(tc.name, func(t *testing.T) {
				file, line, msg := extractBuildFailureLocation(tc.output)

				assert.Equal(t, tc.wantFile, file)
				assert.Equal(t, tc.wantLine, line)
				assert.Equal(t, tc.wantMsg, msg)
			})
		}
	})
}

func TestEscapeData(t *testing.T) {
	t.Run("workflow コマンドのメッセージ本文エスケープ", func(t *testing.T) {
		cases := []struct {
			name  string
			input string
			want  string
		}{
			{name: "% を含むとき、%25 に置換される", input: "100%失敗", want: "100%25失敗"},
			{name: "改行 (LF) を含むとき、%0A に置換される", input: "1行目\n2行目", want: "1行目%0A2行目"},
			{name: "復帰 (CR) を含むとき、%0D に置換される", input: "1行目\r2行目", want: "1行目%0D2行目"},
		}

		for _, tc := range cases {
			t.Run(tc.name, func(t *testing.T) {
				assert.Equal(t, tc.want, escapeData(tc.input))
			})
		}
	})
}

func TestEscapeProperty(t *testing.T) {
	t.Run("workflow コマンドのプロパティ値エスケープ", func(t *testing.T) {
		cases := []struct {
			name  string
			input string
			want  string
		}{
			{name: "コロンを含むとき、%3A に置換される", input: "internal/service:foo", want: "internal/service%3Afoo"},
			{name: "カンマを含むとき、%2C に置換される", input: "a,b.go", want: "a%2Cb.go"},
		}

		for _, tc := range cases {
			t.Run(tc.name, func(t *testing.T) {
				assert.Equal(t, tc.want, escapeProperty(tc.input))
			})
		}
	})
}

func TestReadModulePath(t *testing.T) {
	t.Run("go.mod からのモジュールパス取得", func(t *testing.T) {
		t.Run("module 行があるとき、モジュールパスが返る", func(t *testing.T) {
			dir := t.TempDir()
			writeFile(t, path.Join(dir, "go.mod"), "module github.com/kenyamaneko/example\n\ngo 1.22\n")

			got, err := readModulePath(dir)

			require.NoError(t, err)
			assert.Equal(t, "github.com/kenyamaneko/example", got)
		})

		t.Run("go.mod が存在しないとき、エラーになる", func(t *testing.T) {
			dir := t.TempDir()

			_, err := readModulePath(dir)

			assert.Error(t, err)
		})

		t.Run("module 行が無いとき、エラーになる", func(t *testing.T) {
			dir := t.TempDir()
			writeFile(t, path.Join(dir, "go.mod"), "go 1.22\n")

			_, err := readModulePath(dir)

			assert.Error(t, err)
		})
	})
}

func writeFile(t *testing.T, p, content string) {
	t.Helper()
	require.NoError(t, os.WriteFile(p, []byte(content), 0o644))
}
