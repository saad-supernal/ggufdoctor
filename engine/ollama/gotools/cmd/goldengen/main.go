// goldengen renders every Ollama .gotmpl in DIR against every fixture in
// CORPUS through Ollama's own template package and prints goldens JSON.
//
//	goldengen DIR CORPUS.json OLLAMA_COMMIT
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/ollama/ollama/api"
	"github.com/ollama/ollama/template"
)

type fixture struct {
	Name    string `json:"name"`
	Context struct {
		Messages       []api.Message `json:"messages"`
		Tools          api.Tools     `json:"tools"`
		EnableThinking *bool         `json:"enable_thinking"`
	} `json:"context"`
}

func main() {
	if len(os.Args) != 4 {
		fmt.Fprintln(os.Stderr, "usage: goldengen DIR CORPUS.json OLLAMA_COMMIT")
		os.Exit(2)
	}
	dir, corpusPath, commit := os.Args[1], os.Args[2], os.Args[3]
	var corpus struct {
		Version  string            `json:"version"`
		Fixtures []json.RawMessage `json:"fixtures"`
	}
	b, err := os.ReadFile(corpusPath)
	if err != nil {
		panic(err)
	}
	if err := json.Unmarshal(b, &corpus); err != nil {
		panic(err)
	}
	files, _ := filepath.Glob(filepath.Join(dir, "*.gotmpl"))
	sort.Strings(files)
	renders := map[string]map[string]any{}
	for _, fp := range files {
		name := strings.TrimSuffix(filepath.Base(fp), ".gotmpl")
		src, err := os.ReadFile(fp)
		if err != nil {
			panic(err)
		}
		t, err := template.Parse(strings.ReplaceAll(string(src), "\r\n", "\n"))
		if err != nil {
			renders[name] = map[string]any{"_parse_error": err.Error()}
			continue
		}
		per := map[string]any{}
		for _, raw := range corpus.Fixtures {
			var f fixture
			if err := json.Unmarshal(raw, &f); err != nil {
				var n struct {
					Name string `json:"name"`
				}
				_ = json.Unmarshal(raw, &n)
				per[n.Name] = map[string]string{"unrepresentable": err.Error()}
				continue
			}
			v := template.Values{Messages: f.Context.Messages, Tools: f.Context.Tools}
			if f.Context.EnableThinking != nil {
				v.Think, v.IsThinkSet = *f.Context.EnableThinking, true
			}
			var buf bytes.Buffer
			if err := t.Execute(&buf, v); err != nil {
				per[f.Name] = map[string]string{"error": err.Error()}
				continue
			}
			per[f.Name] = buf.String()
		}
		renders[name] = per
	}
	out := struct {
		OllamaCommit  string                    `json:"ollama_commit"`
		CorpusVersion string                    `json:"corpus_version"`
		Renders       map[string]map[string]any `json:"renders"`
	}{commit, corpus.Version, renders}
	enc := json.NewEncoder(os.Stdout)
	enc.SetEscapeHTML(false)
	enc.SetIndent("", " ")
	if err := enc.Encode(out); err != nil {
		panic(err)
	}
}
