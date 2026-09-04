// namedcheck runs Ollama's real template.Named over templates read as a JSON
// array from stdin and prints [{"name": ..., "distance": ...}] -- the name
// Named returned (null when it returned an error) and the exact minimum
// Levenshtein distance over the index, computed with the same package.
package main

import (
	"encoding/json"
	"math"
	"os"

	"github.com/agnivade/levenshtein"
	"github.com/ollama/ollama/template"
)

type result struct {
	Name     *string `json:"name"`
	Distance int     `json:"distance"`
}

func main() {
	var inputs []string
	if err := json.NewDecoder(os.Stdin).Decode(&inputs); err != nil {
		panic(err)
	}
	indexBytes, err := os.ReadFile(os.Args[1]) // path to template/index.json at the pin
	if err != nil {
		panic(err)
	}
	var index []struct {
		Name     string `json:"name"`
		Template string `json:"template"`
	}
	if err := json.Unmarshal(indexBytes, &index); err != nil {
		panic(err)
	}
	out := make([]result, 0, len(inputs))
	for _, s := range inputs {
		best := math.MaxInt
		for _, e := range index {
			if d := levenshtein.ComputeDistance(s, e.Template); d < best {
				best = d
			}
		}
		r := result{Distance: best}
		if t, err := template.Named(s); err == nil {
			n := t.Name
			r.Name = &n
		}
		out = append(out, r)
	}
	enc := json.NewEncoder(os.Stdout)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(out); err != nil {
		panic(err)
	}
}
