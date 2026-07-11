using System.Xml.Linq;
using TestReport;

if (args.Length < 2)
{
    Console.Error.WriteLine("usage: TestReport <search-root> <title>");
    return 1;
}

var searchRoot = args[0];
var title = args[1];
var workspace = Environment.GetEnvironmentVariable("GITHUB_WORKSPACE")
    ?? throw new InvalidOperationException("GITHUB_WORKSPACE is empty");

// dotnet test はソリューション内のテストプロジェクトごとに別々の TRX を
// <プロジェクト>/TestResults/ 配下へ出力する (--results-directory で1か所に
// 集約すると同名ファイルが上書きされ結果が失われるため使わない)。配下を
// 再帰的に探索して全 TRX を集計する。
var trxPaths = Directory.GetFiles(searchRoot, "*.trx", SearchOption.AllDirectories);
if (trxPaths.Length == 0)
{
    Console.Error.WriteLine($"TestReport: no .trx files found under {searchRoot}");
    return 1;
}

var results = trxPaths
    .SelectMany(trxPath =>
    {
        try
        {
            return TrxReport.Parse(XDocument.Load(trxPath), workspace);
        }
        catch (Exception ex)
        {
            throw new InvalidOperationException($"failed to parse {trxPath}: {ex.Message}", ex);
        }
    })
    .ToList();

var passed = results.Count(r => r.Outcome == TestOutcome.Passed);
var skipped = results.Count(r => r.Outcome == TestOutcome.Skipped);
var failures = results.Where(r => r.Outcome == TestOutcome.Failed).ToList();

WriteSummary(title, passed, failures.Count, skipped, failures);
WriteAnnotations(failures);
return 0;

static void WriteSummary(string title, int passed, int failed, int skipped, IReadOnlyList<TestResult> failures)
{
    var summaryPath = Environment.GetEnvironmentVariable("GITHUB_STEP_SUMMARY");
    if (string.IsNullOrEmpty(summaryPath))
    {
        return;
    }

    var lines = new List<string>
    {
        $"## {title}",
        "",
        "| 項目 | 件数 |",
        "|---|---|",
        $"| 通過 | {passed} |",
        $"| 失敗 | {failed} |",
        $"| スキップ | {skipped} |",
    };
    if (failed > 0)
    {
        lines.Add("");
        lines.Add("失敗したテスト:");
        lines.Add("");
        lines.AddRange(failures.Select(f => $"- {f.Name}"));
    }
    lines.Add("");

    File.AppendAllLines(summaryPath, lines);
}

static void WriteAnnotations(IReadOnlyList<TestResult> failures)
{
    foreach (var f in failures)
    {
        var message = TrxReport.EscapeData($"{f.Name}: {f.Message ?? "failed"}");
        if (f.File is { } file && f.Line > 0)
        {
            Console.WriteLine($"::error file={TrxReport.EscapeProperty(file)},line={f.Line}::{message}");
        }
        else
        {
            Console.WriteLine($"::error::{message}");
        }
    }
}
