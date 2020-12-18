
define(["ace", "repl"], (ace, repl) => {
    let Range = ace.require('ace/range').Range;

    class ReadOnlyEditor {
        constructor(element, options) {
            element.className = "snek-bedit-readonly";

            let edelem = document.createElement("div");
            edelem.className = "snek-bedit-editor";
            edelem.onclick = event => {};

            let status = document.createElement("div");
            status.className = "snek-bedit-status";

            element.appendChild(edelem);
            element.appendChild(status);

            this.status = status
            this.element = element;
            let editor = ace.edit(edelem);
            this.editor = editor;
            editor.setOptions({
                showLineNumbers: false,
                showGutter: false,
                displayIndentGuides: false,
                showPrintMargin: false,
                highlightActiveLine: false,
                minLines: 7,
                maxLines: 7,
                readOnly: true,
            });
            editor.setTheme("ace/theme/xcode");
            editor.session.setMode("ace/mode/python");
            this.update(
                options.content,
                options.filename,
                options.firstlineno,
                options.highlight
            );
        }

        unmark() {
            if (this.mark) {
                this.editor.session.removeMarker(this.mark);
                this.mark = null;
            }
        }

        update(new_content, filename, firstlineno, highlight) {
            this.unmark();
            this.filename = filename;
            this.firstlineno = firstlineno;
            highlight -= firstlineno;
            this.editor.session.removeMarker(this.mark);
            this.editor.setValue(new_content, -1);
            this.status.innerText = filename;
            if (highlight !== null && highlight !== undefined) {
                let range = new Range(highlight, 0, highlight, 1);
                this.mark = this.editor.session.addMarker(
                    range, "snek-bedit-hl", "fullLine"
                );
                this.editor.moveCursorTo(highlight, 0);
                setTimeout(
                    () => { this.editor.scrollToLine(highlight - 3); },
                    0
                )
            }
        }
    }

    return ReadOnlyEditor;
});
