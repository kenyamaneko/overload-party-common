using System.Xml.Linq;
using TestReport;

if (args.Length < 2)
{
    Console.Error.WriteLine("usage: TestReport <trx-path> <title>");
    return 1;
}

var trxPath = args[0];
var title = args[1];
var workspace = Environment.GetEnvironmentVariable("GITHUB_WORKSPACE")
    ?? throw new InvalidOperationException("GITHUB_WORKSPACE is empty");

XDocument trx;
try
{
    trx = XDocument.Load(trxPath);
}
catch (Exception ex)
{
    Console.Error.WriteLine($"TestReport: failed to open {trxPath}: {ex.Message}");
    return 1;
}

var results = TrxReport.Parse(trx, workspace);

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
