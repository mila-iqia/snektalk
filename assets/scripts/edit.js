
define(["ace", "repl"], function(ace, repl) {
    let Range = ace.require('ace/range').Range;

    class EditorPool {
        constructor() {
            this.editors = {};
        }

        add(funcId, editor) {
            let existing = this.editors[funcId];
            if (existing === undefined) {
                existing = [];
                this.editors[funcId] = existing;
            }
            existing.push(new WeakRef(editor));
        }

        signal(funcId, content, status) {
            for (let editor_ref of (this.editors[funcId] || [])) {
                let editor = editor_ref.deref();
                if (editor) {
                    editor.notify(content, status);
                }
            }
        }
    }

    let editors = new EditorPool();

    class BackedEditor {
        constructor(element, options) {
            this.element = element;

            let edelem = document.createElement("div");
            edelem.className = "pf-bedit-editor"
            edelem.onclick = event => {}

            let status = document.createElement("div");
            status.className = "pf-bedit-status"

            let status_filename = document.createElement("div");
            status_filename.className = "pf-bedit-filename"
            status_filename.innerText = options.filename;

            let status_state = document.createElement("div");
            status_state.className = "pf-bedit-state"
            status_state.innerText = "live, saved on disk"
            this.status_state = status_state;

            status.appendChild(status_filename)
            status.appendChild(status_state)

            element.appendChild(edelem);
            element.appendChild(status);

            let editor = ace.edit(edelem);
            // ace.$$allEditors.push(new WeakRef(editor));
            repl.allEditors.push(new WeakRef(editor));
            this.editor = editor;
            editor.setOptions({
                showLineNumbers: false,
                showGutter: false,
                displayIndentGuides: false,
                showPrintMargin: false,
                highlightActiveLine: false,
                maxLines: 30,
            });
            editor.setTheme("ace/theme/xcode");
            editor.session.setMode("ace/mode/python");

            editor.commands.addCommand({
                name: "save",
                bindKey: "Cmd+S",
                exec: async editor => {
                    let success = await options.save(editor.getValue());
                    if (success) {
                        editors.signal(this.funcId, editor.getValue(), "live");
                    }
                }
            });
            editor.commands.addCommand({
                name: "save-return",
                bindKey: "Ctrl+Enter",
                exec: async editor => {
                    let success = await options.save(editor.getValue());
                    if (success) {
                        editors.signal(this.funcId, editor.getValue(), "live");
                        repl.mainRepl.editor.focus();
                    }
                }
            });
            editor.commands.addCommand({
                name: "commit",
                bindKey: "Cmd+Shift+S",
                exec: async editor => {
                    let success = await options.commit(editor.getValue());
                    if (success) {
                        editors.signal(this.funcId, editor.getValue(), "saved");
                    }
                }
            });

            editor.setValue(options.contents, -1);
            if (options.highlight !== null && options.highlight !== undefined) {
                let range = new Range(options.highlight, 0, options.highlight, 1);
                this.mark = editor.session.addMarker(range, "pf-bedit-hl", "fullLine");
            }

            this.funcId = options.funcId;
            this.content = {
                live: options.contents,
                saved: options.contents,
            }
            editors.add(this.funcId, this);
            this.setStatus("saved");

            editor.getSession().on('change', () => {
                if (this.status !== "error") {
                    this.inferStatus();
                }
                if (this.mark) {
                    editor.session.removeMarker(this.mark);
                    this.mark = null;
                }
            });
        }

        inferStatus() {
            let curr = this.editor.getValue();
            if (curr === this.content.live) {
                if (curr === this.content.saved) {
                    this.setStatus("saved");
                }
                else {
                    this.setStatus("live");
                }
            }
            else {
                this.setStatus("dirty");
            }
        }

        setStatus(status) {
            if (this.status === status) {
                return;
            }
            this.element.className = "pf-bedit pf-bedit-" + status;
            if (status === "saved") {
                this.status_state.innerText = "live, saved on disk";
            }
            else if (status === "live") {
                this.status_state.innerText = "live, not saved";
            }
            else if (status === "dirty") {
                this.status_state.innerText = "modified";
            }
            else if (status === "error") {
                this.status_state.innerText = "error";
            }
        }

        notify(content, status) {
            this.content[status] = content;
            this.inferStatus();
        }
    }

    return (...args) => new BackedEditor(...args)
})
