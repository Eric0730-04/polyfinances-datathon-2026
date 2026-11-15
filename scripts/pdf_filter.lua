-- Pandoc filter used by scripts/build_pdfs.sh (PDF output only).
-- 1) Replace the Mermaid diagram with the rendered docs/architecture.png
-- 2) Let long inline code (paths, file names) wrap inside table cells
function CodeBlock(el)
  if el.classes[1] == "mermaid" then
    return pandoc.Para({pandoc.Image({}, "architecture.png")})
  end
end
function Code(el)
  if FORMAT:match("latex") then
    local t = el.text:gsub("\\", "\\textbackslash{}"):gsub("([#$%%&_{}])", "\\%1"):gsub("~", "\\textasciitilde{}")
    t = t:gsub("([/%.]+)", "%1\\allowbreak{}"):gsub("(\\_)", "%1\\allowbreak{}")
    return pandoc.RawInline("latex", "\\texttt{" .. t .. "}")
  end
end
-- 3) Wide tables (7+ columns, e.g. Appendix A): smaller font and sensible column widths
function Table(el)
  if FORMAT:match("latex") and #el.colspecs >= 7 then
    if #el.colspecs == 8 then
      local w = {0.09, 0.23, 0.09, 0.17, 0.07, 0.13, 0.08, 0.14}
      for i, cs in ipairs(el.colspecs) do el.colspecs[i] = {cs[1], w[i]} end
    end
    return {pandoc.RawBlock("latex", "{\\footnotesize"), el, pandoc.RawBlock("latex", "}")}
  end
end
