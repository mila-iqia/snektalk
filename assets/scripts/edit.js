
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

            let save = async (editor, commit) => {
                try {
                    let method = commit ? "commit" : "save";
                    let response = await options[method](editor.getValue());
                    editors.signal(this.funcId, editor.getValue(), "live");
                    if (commit) {
                        editors.signal(this.funcId, editor.getValue(), "saved");
                    }
                    return true;
                }
                catch(exc) {
                    let message = (
                        exc.type === "InvalidSourceException"
                        ? exc.message
                        : `${exc.type}: ${exc.message}`
                    )
                    this.setStatus("error", message);
                    return false;
                }
            }

            editor.commands.addCommand({
                name: "save",
                bindKey: "Cmd+S",
                exec: async editor => {
                    await save(editor, false);
                }
            });

            editor.commands.addCommand({
                name: "save-return",
                bindKey: "Ctrl+Enter",
                exec: async editor => {
                    if (await save(editor, false)) {
                        repl.mainRepl.editor.focus();
                    }
                }
            });

            editor.commands.addCommand({
                name: "commit",
                bindKey: "Cmd+Shift+S",
                exec: async editor => {
                    await save(editor, true);
                }
            });

            editor.setValue(options.content.live, -1);
            if (options.highlight !== null && options.highlight !== undefined) {
                let range = new Range(options.highlight, 0, options.highlight, 1);
                this.mark = editor.session.addMarker(range, "pf-bedit-hl", "fullLine");
                editor.moveCursorTo(options.highlight, 0);
                editor.renderer.scrollCursorIntoView();
            }

            // TODO: Make the range read-only. This is a bit difficult to do
            // with Ace in ways that can't be accidentally defeated. The best
            // approach seems to be to replace insert/remove/etc. functions
            // in editor.session.
            if (options.protectedPrefix) {
                let prot = new Range(0, 0, options.protectedPrefix - 1, 1);
                editor.session.addMarker(prot, "pf-bedit-protected", "fullLine");
            }

            this.funcId = options.funcId;
            this.content = options.content;
            editors.add(this.funcId, this);
            this.inferStatus();

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

        setStatus(status, message) {
            if (this.status === status) {
                return;
            }
            this.status = status;
            this.element.className = "pf-bedit pf-bedit-" + status;
            if (status === "saved") {
                this.status_state.innerText = message || "live, saved on disk";
            }
            else if (status === "live") {
                this.status_state.innerText = message || "live, not saved";
            }
            else if (status === "dirty") {
                this.status_state.innerText = message || "modified";
            }
            else if (status === "error") {
                this.status_state.innerText = message || "error";
            }
        }

        notify(content, status) {
            this.content[status] = content;
            this.inferStatus();
        }
    }

    return BackedEditor;
})
