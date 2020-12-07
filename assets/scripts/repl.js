
import ace from "/scripts/ace/ace.js"

ace.config.set("basePath", "/scripts/ace/")


export class Repl {

    constructor(target) {
        this.pane = target.querySelector(".pf-pane");
        this.pinpane = target.querySelector(".pf-pin-pane");
        this.inputBox = target.querySelector(".pf-input");
        this._setupEditor(this.inputBox);
        this.historyCurrent = 0;
        this.history = [""];
        target.onclick = this.$globalClickEvent.bind(this);
        document.$$PFCB = this.pfcb.bind(this);
    }

    $globalClickEvent(evt) {
        let target = evt.target;
        while (target) {
            if (target.onclick !== null) {
                break;
            }
            else if (evt.metaKey && target.getAttribute("pinnable") !== null) {
                this.pin(target);
            }
            else if (!evt.metaKey && target.getAttribute("objid") !== null) {
                this.pfcb(parseInt(target.getAttribute("objid")));
            }
            target = target.parentElement;
        }
    }

    pfcb(id) {
        // Call a Python function by id
        const exec = (...args) => {
            this.send({
                command: "callback",
                id: id,
                arguments: args
            });
        }
        let evt = window.event;

        if (evt === undefined) {
            // If not in an event handler, we return the execution
            // function directly
            return exec;
        }
        else {
            // The call is in an event handler like onclick, for example
            // <div onclick="$$PFCB(15)">...</div>, so we execute it
            // immediately.
            evt.preventDefault();
            evt.stopPropagation();
            exec({
                type: evt.type,
                button: evt.button,
                shiftKey: evt.shiftKey,
                altKey: evt.altKey,
                ctrlKey: evt.ctrlKey,
                metaKey: evt.metaKey,
                key: evt.key,
                offsetX: evt.offsetX,
                offsetY: evt.offsetY,
            });
        }
    }

    pin(elem) {
        if (!elem.$referenceParent) {
            elem.$referenceParent = elem.parentElement;
        }
        let parent = elem.$referenceParent;

        let make_button = () => {
            let pinbutton = document.createElement("span");
            pinbutton.className = "pf-pinbutton";
            pinbutton.innerHTML = `<svg width="24" height="24" fill="#aaa" transform="scale(0.75, 0.75)" viewBox="0 0 1000 1000" xmlns="http://www.w3.org/2000/svg"><path d=" M 725 88C 746 88 762 104 763 125C 763 125 763 188 763 188C 763 242 725 287 675 287C 675 287 641 287 641 287C 641 287 659 466 659 466C 690 473 717 489 734 513C 756 544 763 583 763 625C 762 646 746 662 725 663C 725 663 600 663 600 663C 600 663 563 663 563 663C 563 663 437 663 437 663C 437 663 400 663 400 663C 400 663 275 663 275 663C 254 662 238 646 238 625C 238 583 244 544 266 513C 283 489 310 473 341 466C 341 466 359 287 359 287C 359 287 325 287 325 287C 300 287 279 276 264 261C 249 246 238 225 238 200C 238 158 238 167 238 125C 238 104 254 88 275 88C 275 88 725 88 725 88M 563 710C 563 710 563 850 563 850C 563 856 561 862 559 867C 559 867 534 917 534 917C 527 929 514 937 500 937C 486 937 473 929 466 917C 466 917 441 867 441 867C 439 862 438 856 437 850C 437 850 437 710 437 710C 437 710 563 710 563 710"/></svg>`
            pinbutton.onclick = event => {
                event.preventDefault();
                event.stopPropagation();
                this.pin(elem);
            }
            return pinbutton;    
        }

        if (!elem.$pinned) {
            let wrapper = document.createElement("div");
            if (!elem.$onclick) {
                elem.$onclick = elem.onclick;
            }
            let pinbutton = make_button();
            parent.replaceChild(pinbutton, elem);
            this.pinpane.appendChild(wrapper);
            wrapper.appendChild(elem);
            elem.$wrapper = wrapper;
            elem.$pinned = pinbutton;
        }
        else {
            this.pinpane.removeChild(elem.$wrapper);
            parent.replaceChild(elem, elem.$pinned);
            elem.$pinned = false;
        }
    }

    _setupEditor(target) {
        let editor = ace.edit(target);
        editor.setOptions({
            showLineNumbers: false,
            showGutter: false,
            displayIndentGuides: false,
            showPrintMargin: false,
            highlightActiveLine: false,
            maxLines: 10,
        });
        editor.setTheme("ace/theme/xcode");
        editor.session.setMode("ace/mode/python");

        let _submit = () => {
            let val = editor.getValue();
            editor.setValue("");
            this.send({
                command: "submit",
                expr: val,
            });
            this.history[0] = val;
            this.history.unshift("");
            this.historyCurrent = 0;
        }

        editor.commands.addCommand({
            name: "maybe-submit",
            bindKey: "Enter",
            exec: editor => {
                let value = editor.getValue();
                if (value.trim() === "") {
                    return;
                }
                let lines = value.split("\n");
                if (lines.length == 1 && !lines[0].match(/[\(\[\{:]$/)) {
                    _submit();
                }
                else {
                    editor.session.insert(editor.getCursorPosition(), "\n ");
                    editor.selection.selectLine();
                    editor.autoIndent();
                }
            }
        });

        editor.commands.addCommand({
            name: "submit",
            bindKey: "Ctrl+Enter",
            exec: editor => {
                _submit();
            }
        });

        editor.commands.addCommand({
            name: "clear",
            bindKey: "Ctrl+L",
            exec: editor => {
                this.pane.innerHTML = "";
            }
        });

        editor.commands.addCommand({
            name: "history-previous",
            bindKey: "Up",
            exec: editor => {
                if (editor.getCursorPosition().row === 0) {
                    this.historyShift(-1);
                }
                else {
                    editor.navigateUp(1);
                }
            }
        });

        editor.commands.addCommand({
            name: "history-next",
            bindKey: "Down",
            exec: editor => {
                let nlines = editor.getValue().split("\n").length;
                if (editor.getCursorPosition().row === nlines - 1) {
                    this.historyShift(1);
                }
                else {
                    editor.navigateDown(1);
                }
            }
        });

        this.editor = editor;
    }

    historyShift(delta) {
        if (this.historyCurrent === 0) {
            this.history[0] = this.editor.getValue();
        }
        let n = this.history.length;
        let new_position = (this.historyCurrent - delta + n) % n;
        if (new_position !== this.historyCurrent) {
            this.historyCurrent = new_position;
            // The -delta will put the cursor at the beginning if we come
            // from above, at the end if we come from below
            this.editor.setValue(this.history[this.historyCurrent], -delta);
            // We still want to be at the end of the line, though:
            this.editor.navigateLineEnd();
        }
    }

    reify(html) {
        let rval = document.createElement("div");
        rval.innerHTML = html;
        return rval;
    }

    read_only_editor(text) {
        let elem = document.createElement("div");
        elem.style.width = this.pane.offsetWidth - 100;
        let editor = ace.edit(elem)
        editor.setValue(text, -1);
        editor.setTheme("ace/theme/xcode");
        editor.session.setMode("ace/mode/python");
        editor.setOptions({
            showLineNumbers: false,
            showGutter: false,
            displayIndentGuides: false,
            showPrintMargin: false,
            highlightActiveLine: false,
            minLines: 1,
            maxLines: 10,
            readOnly: true,
        });
        editor.renderer.$cursorLayer.element.style.display = "none";
        return elem;
    }
    
    send(message) {
        // Send a message to PythonFace
        this.socket.send(JSON.stringify(message));
    }

    append(elem, type) {
        let wrapper = document.createElement("div");
        wrapper.className = "pf-line pf-t-" + type;
        let gutter = document.createElement("div");
        gutter.className = "pf-gutter pf-t-" + type;
        wrapper.appendChild(gutter);
        wrapper.appendChild(elem);
        this.pane.appendChild(wrapper);
        return wrapper;
    }

    process_message(data) {
        if (data.command == "resource") {
            let elem = this.reify(data.value);
            document.head.appendChild(elem);
        }
        else if (data.command == "result") {
            let elem = this.reify(data.value);
            let prbox = null;
            if (data.evalid !== undefined) {
                prbox = document.getElementById("pr-eval-" + data.evalid);
                if (prbox === null) {
                    prbox = document.createElement("div");
                    prbox.id = "pr-eval-" + data.evalid;
                    this.append(prbox, "print");
                }
            }
            if (data.type === "statement") { }
            else if (data.type === "print") {
                prbox.appendChild(elem);
            }
            else {
                this.append(elem, data.type);
            }
        }
        else if (data.command == "echo") {
            let ed = this.read_only_editor(data.value.trimEnd());
            let elem = document.createElement("div");
            elem.appendChild(ed);
            this.append(elem, "echo");
        }
        else if (data.command == "pastevar") {
            let varname = data.value;
            this.editor.session.insert(this.editor.getCursorPosition(), varname);
            this.editor.focus();
        }
        else {
            console.error("Received an unknown command:", data.command);
        }
    }

    connect() {
        let socket = new WebSocket('ws://localhost:6499/pf?session=main');

        socket.addEventListener('message', event => {
            let data = JSON.parse(event.data);
            this.process_message(data);
        });

        this.socket = socket;
    }

    getEditor() {
        return editor;
    }

}
