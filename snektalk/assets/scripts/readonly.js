
require.config({ paths: { "vs": "/lib/vs" }});
define(["vs/editor/editor.main"], (monaco) => {

    class ReadOnlyEditor {
        constructor(element, options) {
            this.element = element;
            this.options = options;

            this.setupElement();
            this.setupEditor();

            this.update(
                this.options.content,
                this.options.filename,
                this.options.firstlineno,
                this.options.highlight
            );
        }

        setupElement() {
            this.element.className = "snek-bedit-readonly";

            let container = document.createElement("div");
            container.className = "snek-bedit-editor";
            container.onclick = _ => {};
            this.container = container;

            let status = document.createElement("div");
            status.className = "snek-bedit-status";
            this.status = status;

            this.element.appendChild(container);
            this.element.appendChild(status);
        }

        setupEditor() {
            this.container.style.height = (19 * 7) + "px";
            this.editor = monaco.editor.create(this.container, {
                value: "",
                language: 'python',
                lineNumbers: false,
                minimap: {enabled: false},
                scrollBeyondLastLine: false,
                overviewRulerLanes: 0,
                folding: false,
                readOnly: true,
            });
            this.hl = [];
        }

        update(new_content, filename, firstlineno, highlight) {
            this.filename = filename;
            this.firstlineno = firstlineno;
            highlight -= firstlineno;
            this.editor.setValue(new_content);
            this.status.innerText = filename;
            this.editor.updateOptions({
                lineNumbers: i => i + firstlineno - 1
            });
            if (highlight !== null) {
                this.hl = this.editor.deltaDecorations(this.hl, [
                    {
                        range: new monaco.Range(highlight + 1,1,highlight + 1,1),
                        options: { isWholeLine: true, className: 'snek-bedit-hl' }
                    },
                ]);
                this.editor.revealLineInCenter(highlight + 1);
            }
        }
    }

    return ReadOnlyEditor;
});
