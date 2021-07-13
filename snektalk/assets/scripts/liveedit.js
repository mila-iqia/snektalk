
require.config({ paths: { 'vs': '/lib/vs' }});
define(["vs/editor/editor.main", "scripts/repl"], (monaco, repl) => {
    const KM = monaco.KeyMod;
    const KC = monaco.KeyCode;

    class LiveEditor {
        constructor(element, options) {
            this.element = element;
            this.options = options;
            this.content = options.content;

            this.setupElement();
            this.setupEditor();
            this.inferStatus();

            if (this.options.autofocus) {
                this.editor.focus();
            }
        }

        setupElement() {
            let container = document.createElement("div");
            container.className = "snek-bedit-editor snek-editor-cyclable"
            container.onclick = _ => {}
            this.container = container

            let status = document.createElement("div");
            status.className = "snek-bedit-status"

            let status_filename = document.createElement("div");
            status_filename.className = "snek-bedit-filename"
            status_filename.innerText = this.options.filename;

            let status_state = document.createElement("div");
            status_state.className = "snek-bedit-state"
            status_state.innerText = "live, saved on disk"
            this.status_state = status_state;

            status.appendChild(status_filename)
            status.appendChild(status_state)

            this.element.appendChild(container);
            this.element.appendChild(status);
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
            this.status = status;
            this.element.className = "snek-bedit snek-bedit-" + status;
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

        async save(commit) {
            try {
                let method = commit ? "commit" : "save";
                let value = this.editor.getValue()
                let response = await this.options.py[method](value);
                this.content.live = value
                if (commit) {
                    this.content.saved = value
                }
                this.inferStatus();
                return true;
            }
            catch(exc) {
                let message = (
                    exc.type === "InvalidSourceException"
                    ? exc.message
                    : `${exc.type}: ${exc.message}`
                );
                this.setStatus("error", message);
                return false;
            }
        }

        setupEditor() {
            this.editor = monaco.editor.create(this.container, {
                value: this.content.live,
                language: 'python',
                lineNumbers: false,
                minimap: {enabled: false},
                scrollBeyondLastLine: false,
                overviewRulerLanes: 0,
                folding: false,
                automaticLayout: true,
            });
            this.container.$editor = this.editor;

            this.editor.onDidContentSizeChange(this.event_updateHeight.bind(this));
            this.event_updateHeight();

            this.editor.addCommand(
                KM.CtrlCmd | KC.KEY_S,
                this.command_save.bind(this)
            );
            this.editor.addCommand(
                KM.CtrlCmd | KM.Shift | KC.KEY_S,
                this.command_commit.bind(this)
            );
            this.editor.addCommand(
                KM.WinCtrl | KC.Enter,
                this.command_save_and_repl.bind(this)
            );
            this.editor.addCommand(
                KM.WinCtrl | KM.Shift | KC.Enter,
                this.command_commit_and_repl.bind(this)
            );
            this.editor.addCommand(
                KM.CtrlCmd | KC.KEY_R,
                this.command_reset_to_saved.bind(this)
            );

            if (this.options.highlight !== null) {
                var hl = this.editor.deltaDecorations([], [
                    { range: new monaco.Range(this.options.highlight + 1,1,this.options.highlight + 1,1), options: { isWholeLine: true, className: 'snek-bedit-hl' }},
                ]);
                this.editor.revealLineInCenter(this.options.highlight + 1);
                this.editor.getModel().onDidChangeContent(
                    () => {
                        hl = this.editor.deltaDecorations(hl, []);
                    }
                )
            }

            this.editor.getModel().onDidChangeContent(
                () => {
                    if (this.status !== "error") {
                        this.inferStatus();
                    }
                }
            )

            function selectedWord(ed) {
                // Send the selection, or the word under the cursor if
                // there is no selection. I'm sure there's an actual
                // function somewhere in monaco to do this, because this
                // is how actions that need a selection seem to already
                // work, but finding it seems more time consuming than
                // implementing it.
                const model = ed.getModel();
                let sel = ed.getSelection();
                if (sel.startLineNumber === sel.endLineNumber
                    && sel.startColumn === sel.endColumn) {

                    const pos = ed.getPosition();
                    const word = model.getWordAtPosition(pos);
                    sel = {
                        startLineNumber: pos.lineNumber,
                        startColumn: word.startColumn,
                        endLineNumber: pos.lineNumber,
                        endColumn: word.endColumn,
                    }
                }
                return sel;
            }

            this.editor.addAction({
                id: 'sktk-probe',
                label: 'Probe',
                keybindings: [KM.chord(KM.CtrlCmd | KM.Alt | KC.KEY_P, KC.KEY_P)],
                precondition: null,
                keybindingContext: null,
                contextMenuGroupId: '99_probe',
                contextMenuOrder: 1,
                run: ed => {
                    this.options.py.probe(selectedWord(ed));
                }
            });

            this.editor.addAction({
                id: 'sktk-local-probe',
                label: 'Local probe',
                keybindings: [KM.chord(KM.CtrlCmd | KM.Alt | KC.KEY_P, KC.KEY_L)],
                precondition: null,
                keybindingContext: null,
                contextMenuGroupId: '99_probe',
                contextMenuOrder: 1,
                run: ed => {
                    this.options.py.local_probe(selectedWord(ed));
                }
            });

            this.editor.addAction({
                id: 'sktk-explore',
                label: 'Explore',
                keybindings: [KM.chord(KM.CtrlCmd | KM.Alt | KC.KEY_P, KC.KEY_E)],
                precondition: null,
                keybindingContext: null,
                contextMenuGroupId: '99_probe',
                contextMenuOrder: 1,
                run: ed => {
                    this.options.py.explore(selectedWord(ed));
                }
            });

            this.editor.addAction({
                id: 'sktk-local-explore',
                label: 'Local explore',
                keybindings: [KM.chord(KM.CtrlCmd | KM.Alt | KC.KEY_P, KC.KEY_X)],
                precondition: null,
                keybindingContext: null,
                contextMenuGroupId: '99_probe',
                contextMenuOrder: 1,
                run: ed => {
                    this.options.py.local_explore(selectedWord(ed));
                }
            });

            this.editor.addAction({
                id: 'sktk-accumulate',
                label: 'Accumulate',
                keybindings: [KM.chord(KM.CtrlCmd | KM.Alt | KC.KEY_P, KC.KEY_A)],
                precondition: null,
                keybindingContext: null,
                contextMenuGroupId: '99_probe',
                contextMenuOrder: 1,
                run: ed => {
                    this.options.py.accumulate(selectedWord(ed));
                }
            });
        }

        event_updateHeight() {
            const contentHeight = Math.min(
                this.options.max_height || 500,
                this.editor.getContentHeight()
            );
            this.container.style.height = `${contentHeight}px`;
            // Normally the relayout should be automatic, but doing it here
            // avoids some flickering
            this.editor.layout({
                width: this.container.offsetWidth - 10,
                height: contentHeight
            });
        }

        async command_save() {
            await this.save(false);
        }
        
        async command_commit() {
            await this.save(true);
        }

        async command_save_and_repl() {
            if (await this.save(false)) {
                repl.mainRepl.editor.focus();
            }
        }
        
        async command_commit_and_repl() {
            if (await this.save(true)) {
                repl.mainRepl.editor.focus();
            }
        }

        async command_reset_to_saved() {
            this.editor.setValue(this.content.saved);
            this.inferStatus();
        }

    }
    return LiveEditor;
});
