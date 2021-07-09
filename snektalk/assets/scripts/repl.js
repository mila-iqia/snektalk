
let isMac = /(Mac|iPhone|iPod|iPad)/i.test(window.navigator.platform);

function activateScripts(node) {
    if (node.tagName === 'SCRIPT') {
        node.parentNode.replaceChild(reScript(node), node);
    }
    else {
        for (let child of node.childNodes) {
            activateScripts(child);
        }
    }
    return node;
}


function reScript(node){
    let script  = document.createElement("script");
    script.text = node.innerHTML;
    for (let attr of node.attributes) {
        script.setAttribute(attr.name, attr.value);
    }
    return script;
}


// Adapted from: https://stackoverflow.com/questions/123999/how-can-i-tell-if-a-dom-element-is-visible-in-the-current-viewport/7557433#7557433
function isElementInViewport(el) {
    var rect = el.getBoundingClientRect();
    return (
        el.offsetWidth > 0
        && el.offsetHeight > 0
        && rect.top >= 0
        && rect.left >= 0
        && rect.bottom <= (window.innerHeight
                          || document.documentElement.clientHeight)
        && rect.right <= (window.innerWidth
                          || document.documentElement.clientWidth)
    );
}

require.config({ paths: { 'vs': '/lib/vs' }});
define(["vs/editor/editor.main"], (monaco) => {

const KM = monaco.KeyMod;
const KC = monaco.KeyCode;

let mainRepl = null;
let evalIdGen = 0;


class PopupNav {
    constructor(options) {
        this.name = options.name;
        this.default = options.default;
        this.anchor = options.anchor;
        this.element = document.createElement("div");
        this.element.classList.add("snek-popup-nav");
        this.element.classList.add(options.class);
        this.anchor.appendChild(this.element);
        this.onselect = options.onselect;
        this.setEntries([]);
        this.visible = true;
    }

    get() {
        const ret = [];
        for (const cursor of this.cursors) {
            const entry = this.entries[cursor];
            if (entry !== undefined) {
                ret.push(entry);
            }
        }
        return ret.reverse();
    }

    submit() {
        this.onselect(this.get());
    }

    setEntries(entries) {
        this.cursors = [];
        this.entries = entries;
        this.element.innerHTML = "";
        for (const entry of entries) {
            const row = document.createElement("div");
            row.classList.add("snek-popup-nav-entry");
            row.innerText = entry.text;
            row.onclick = () => this.onselect([entry]);
            this.element.appendChild(row);
        }
        if (!this.element.children.length) {
            this.element.innerHTML = this.default;
        }
        else {
            this.setCursor([0]);
        }
    }

    updateCursors(new_cursors) {
        const n = this.entries.length;
        if (n === 0) {
            return;
        }
        for (const cursor of this.cursors) {
            if (new_cursors.indexOf(cursor) === -1) {
                this.element.children[cursor].classList.remove("snek-popup-nav-cursor");
            }
        }
        for (const cursor of new_cursors) {
            this.element.children[cursor].classList.add("snek-popup-nav-cursor");
        }
        this.cursors = new_cursors;
    }

    setCursor(value) {
        let new_cursors = [value];
        this.updateCursors(new_cursors);
    }

    addCursor(value) {
        let new_cursors = [value, ...this.cursors];
        new_cursors = [...new Set(new_cursors)];
        new_cursors.sort((x, y) => x - y);
        this.updateCursors(new_cursors);
    }

    goUp(expand) {
        const x = this.cursors.length - 1;
        if (!this.cursors.length && this.entries.length) {
            this.setCursor(0);
        }
        else if (this.cursors.length) {
            const pos = Math.min(this.entries.length - 1, this.cursors[x] + 1);
            if (expand) {
                this.addCursor(pos);
            }
            else {
                this.setCursor(pos);
            }
        }
    }

    goDown(expand) {
        if (!this.cursors.length && this.entries.length) {
            this.setCursor(0);
        }
        else if (this.cursors.length) {
            const pos = Math.max(0, this.cursors[0] - 1);
            if (expand) {
                this.addCursor(pos);
            }
            else {
                this.setCursor(pos);
            }
        }
    }

    show() {
        this.element.style.display = "flex";
        this.visible = true;
    }

    hide() {
        this.element.style.display = "none";
        this.visible = false;
    }
}


class Repl {

    constructor(target) {
        this.container = target;
        this.options = {};
        this.lib = {};
        this.pane = target.querySelector(".snek-pane");
        this.outerPane = target.querySelector(".snek-outer-pane");
        this.pinpane = target.querySelector(".snek-pin-pane");
        this.inputOuter = target.querySelector(".snek-input-box");
        this.inputBox = target.querySelector(".snek-input");
        this.inputMode = target.querySelector(".snek-input-mode");
        this.inputMode.onclick = () => setTimeout(() => {
            this.togglePopup("interactors");
            this.editor.focus();
        }, 0);
        this.statusBar = target.querySelector(".snek-status-bar");
        this.statusBar.onclick = () => this.cmd_status("/status");
        this.nav = target.querySelector(".snek-nav");
        this.statusHistory = document.createElement("div");
        this.statusHistory.className = "snek-status-history";
        this._setupEditor(this.inputBox);

        this.popups = {
            history: new PopupNav({
                name: "history",
                anchor: this.inputOuter,
                onselect: entries => {
                    this.editor.setValue(entries.map(x => x.text).join("\n"));
                    const nlines = this.editor.getModel().getLineCount();
                    this.editor.setPosition({lineNumber: nlines, column: 1000000});
                    this.togglePopup(null);
                    this.editor.focus();
                },
                class: "snek-popup-nav-history",
                default: "No results",
            }),
            interactors: new PopupNav({
                name: "interactors",
                anchor: this.inputOuter,
                onselect: entries => {
                    this.send({
                        command: "submit",
                        expr: `/attach ${entries[0].text}`,
                    });
                    this.togglePopup(null);
                    this.editor.focus();
                },
                class: "snek-popup-nav-interactors",
                default: "No interactors",
            })
        };
        this.togglePopup(null);

        this.historySelection = 0;
        this.filter = null;
        this.filteredHistory = [""];
        this.history = [""];
        this.expectedContent = null;
        this.historyPopup = null;

        target.onclick = this.$globalClickEvent.bind(this);
        window.onkeydown = this.$globalKDEvent.bind(this);
        window.$$SKTK = this.sktk.bind(this);
        window.snektalk = this;
        this.$currid = 0;
        this.$responseMap = {};
        exports.mainRepl = this;
    }

    $globalKDEvent(evt) {
        let cmdctrl = isMac ? (evt.metaKey && !evt.ctrlKey) : evt.ctrlKey;

        // Cmd+P => focus repl
        if (cmdctrl && !evt.altKey && evt.key === "p") {

            evt.preventDefault();
            evt.stopPropagation();

            this.editor.focus();
        }
        // Cmd+B => navigate to next visible editor
        else if (cmdctrl && !evt.altKey && evt.key === "b") {

            evt.preventDefault();
            evt.stopPropagation();
    
            // Find alive and visible editors
            let editors = Array
            .from(this.container.querySelectorAll(".snek-editor-cyclable"))
            .filter(container => isElementInViewport(container))
            .map(container => container.$editor);

            if (!evt.shiftKey) {
                editors.reverse();
            }

            let focused = null;
            for (let editor of editors) {
                if (focused) {
                    editor.focus();
                    return;
                }
                if (editor.hasTextFocus()) {
                    focused = editor;
                }
            }
            if (editors.length > 0) {
                editors[0].focus();
            }
        }
    }

    $globalClickEvent(evt) {
        let cmdctrl = isMac ? (evt.metaKey && !evt.ctrlKey) : evt.ctrlKey;

        if (evt.detail === 2) {
            // Double-click
            return;
        }
        let target = evt.target;
        while (target) {
            if (target.onclick !== null
                || target.onmousedown !== null
                || target.ondblclick !== null
                || target.tagName === "A") {
                // Stop if non-default behavior or link
                break;
            }
            else if (cmdctrl && evt.altKey && !evt.shiftKey && target.getAttribute("pinnable") !== null) {
                this.pin(target);
                break;
            }
            else if (cmdctrl && !evt.altKey && !evt.shiftKey && target.getAttribute("objid") !== null) {
                this.sktk(parseInt(target.getAttribute("objid")));
                break;
            }
            target = target.parentElement;
        }

        while (target) {
            if (target.classList.contains("snek-popup-nav")) {
                return;
            }
            target = target.parentElement;
        }
        this.togglePopup(null);
    }

    get_external(id) {
        return async (...args) => {
            let response_id = this.$currid++;
            let response = new Promise(
                (resolve, reject) => {
                    this.$responseMap[response_id] = {resolve, reject};
                }
            );
            this.send({
                command: "callback",
                id: id,
                response_id: response_id,
                arguments: args
            });
            return await response;
        }
    }

    sktk(id, ...args) {
        // Call a Python function by id
        const exec = this.get_external(id);

        const execNow = async () => {
            try {
                await exec({
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
            catch(exc) {
                let message = `${exc.type}: ${exc.message}`;
                this.setStatus({type: "error", value: message});
                throw exc;
            }
        }

        let evt = window.event;

        if (evt === undefined || evt.type === "load") {
            // If not in an event handler, we return the execution
            // function directly
            return exec;
        }
        else {
            // The call is in an event handler like onclick, for example
            // <div onclick="$$SKTK(15)">...</div>, so we execute it
            // immediately.
            evt.preventDefault();
            evt.stopPropagation();
            execNow();
        }
    }

    pin(elem) {
        if (!elem.$referenceParent) {
            elem.$referenceParent = elem.parentElement;
        }
        let parent = elem.$referenceParent;

        let make_button = () => {
            let pinbutton = document.createElement("span");
            pinbutton.className = "snek-pinbutton";
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

    event_updateHeight() {
        if (!this.ignoreEvent) {
            const contentHeight = Math.min(
                this.options.max_height || 500,
                this.editor.getContentHeight()
            );
            this.inputBox.style.height = `${contentHeight}px`;
            try {
                this.ignoreEvent = true;
                this.editor.layout({ width: this.inputBox.offsetWidth, height: contentHeight });
            } finally {
                this.ignoreEvent = false;
            }
        }
    }

    _setupEditor(target) {
        target.style.height = "19px";
        let editor = monaco.editor.create(target, {
            value: "",
            language: 'python',
            lineNumbers: false,
            minimap: {enabled: false},
            scrollBeyondLastLine: false,
            overviewRulerLanes: 0,
            folding: false,
            renderLineHighlight: "none",
            lineDecorationsWidth: 0,
            suggestOnTriggerCharacters: false,
            wordBasedSuggestions: false,
        });
        this.editor = editor;
        target.classList.add("snek-editor-cyclable");
        target.$editor = this.editor;
        this.editor.onDidContentSizeChange(this.event_updateHeight.bind(this));

        this.popupActive = this.editor.createContextKey("popupActive", false);
        this.atBeginning = this.editor.createContextKey("atBeginning", true);
        this.atEnd = this.editor.createContextKey("atEnd", true);
        this.multiline = this.editor.createContextKey("multiline", false);

        const setMultiline = value => {
            this.multiline.set(value);
            if (value) {
                this.inputBox.classList.add("multiline");
            }
            else {
                this.inputBox.classList.remove("multiline");
            }
        }

        this.editor.onDidChangeCursorPosition(() => {
            let position = editor.getPosition();
            let lineno = position.lineNumber;
            let total = editor.getModel().getLineCount();
            this.atBeginning.set(lineno == 1);
            this.atEnd.set(lineno == total);
        });

        this.editor.getModel().onDidChangeContent(async () => {
            let total = editor.getModel().getLineCount();
            setMultiline(
                total > 1
                || editor.getModel().getLineContent(1).match(/[\(\[\{:]$|^@/)
            )
            let pop = this.activePopup;
            if (pop !== null) {
                pop.setEntries(
                    await this.lib.populate_popup(pop.name, this.editor.getValue())
                );
            }
        });

        let _submit = () => {
            let val = editor.getValue();
            editor.setValue("");
            this.send({
                command: "submit",
                expr: val,
            });
            if (this.history[1] !== val && val !== "") {
                this.history[0] = val;
                this.history.unshift("");
            }
            else {
                this.history[0] = "";
            }
            this.filter = null;
            this.togglePopup(null);
            // The flex-direction on the outer pane is reversed, so
            // 0 scrolls it to the bottom. Handy.
            this.outerPane.scrollTop = 0;
        }

        editor.addCommand(
            KC.Enter,
            _submit,
            "!multiline && !popupActive"
        );

        editor.addCommand(
            KM.WinCtrl | KC.Enter,
            _submit
        );

        editor.addCommand(
            KM.WinCtrl | KC.KEY_L,
            () => { this.pane.innerHTML = ""; }
        );

        editor.addCommand(
            KM.WinCtrl | KC.KEY_R,
            () => this.togglePopup("history")
        );

        editor.addCommand(
            KC.UpArrow,
            () => { this.navigateHistory(-1); },
            "atBeginning && !popupActive"
        );

        editor.addCommand(
            KC.DownArrow,
            () => { this.navigateHistory(1); },
            "atEnd && !popupActive"
        );

        // Bindings when popup is active

        editor.addCommand(
            KC.Enter,
            () => this.activePopup.submit(),
            "popupActive"
        );

        editor.addCommand(
            KC.Escape,
            () => this.togglePopup(null),
            "popupActive"
        );

        editor.addCommand(
            KC.UpArrow,
            () => { this.activePopup.goUp(); },
            "popupActive"
        );

        editor.addCommand(
            KC.DownArrow,
            () => { this.activePopup.goDown(); },
            "popupActive"
        );

        editor.addCommand(
            KM.Shift | KC.UpArrow,
            () => { this.activePopup.goUp(true); },
            "popupActive"
        );

        editor.addCommand(
            KM.Shift | KC.DownArrow,
            () => { this.activePopup.goDown(true); },
            "popupActive"
        );

        // Misc

        editor.addCommand(
            KM.Alt | KC.US_SEMICOLON,
            () => { this.editor.trigger(null, "editor.action.commentLine"); },
        );

        editor.addCommand(
            KM.chord(KM.CtrlCmd | KC.KEY_K, KM.CtrlCmd | KC.KEY_K),
            () => {
                this.editor.setValue("");
                this.lib.stop();
            }
        );

        if (isMac) {
            editor.addCommand(
                KM.WinCtrl | KC.KEY_C,
                () => {
                    this.editor.setValue("");
                    this.lib.stop();
                }
            );
        }

        this.editor = editor;
    }

    async togglePopup(name) {
        this.activePopup = null;
        for (const popupName in this.popups) {
            const pop = this.popups[popupName];
            if (name == popupName && !pop.visible) {
                const entries = await this.lib.populate_popup(name, this.editor.getValue());
                if (entries !== null) {
                    pop.setEntries(entries);
                }
                pop.show();
                if (!pop.entries.length) {
                    pop.setCursor(0);
                }
                this.activePopup = pop;
            }
            else {
                pop.hide();
            }
        }
        this.popupActive.set(this.activePopup !== null);
    }

    async navigateHistory(delta) {
        const text = (await this.lib.history_navigate(delta, this.editor.getValue()));
        if (text !== null) {
            this.expectedContent = text;
            this.editor.setValue(text);

            if (delta < 0) {
                let nlines = this.editor.getModel().getLineCount();
                this.editor.setPosition({lineNumber: nlines, column: 1000000});
            }
            else {
                this.editor.setPosition({lineNumber: 1, column: 1000000});
            }
        }
    }

    reify(html) {
        let rval = document.createElement("div");
        rval.innerHTML = html;
        activateScripts(rval);
        return rval;
    }

    read_only_editor(text, language) {
        let elem = document.createElement("div");
        elem.style.width = this.pane.offsetWidth - 100;

        monaco.editor
        .colorize(text, language)
        .then(result => { elem.innerHTML = result; });

        return elem;
    }

    find_method(prefix, name, dflt) {
        let method_name = `${prefix}_${name}`;
        let method = this[method_name] || dflt;
        return method && method.bind(this);
    }

    send(data) {
        this.find_method("send", data.command, this.send_default)(data);
    }

    send_submit(data) {
        let cmd = /^\/([^ ]+)( .*)?/.exec(data.expr);
        let method = cmd && this.find_method("cmd", cmd[1], null);
        if (method !== null) {
            method(cmd[0], cmd[2]);
        }
        else {
            this.send_default(data);
        }
    }

    send_default(data) {
        if (this.closed) {
            this.setStatus({
                type: "error",
                value: "operation failed because the connection is closed",
            });
        }
        else {
            this.socket.send(JSON.stringify(data));
        }
    }

    cmd_status(fullexpr, arg) {
        this.recv_echo({value: fullexpr});
        this.append(this.statusHistory, "plain");
    }

    append(elem, type, target) {
        let wrapper = document.createElement("div");
        wrapper.className = "snek-line snek-t-" + type;
        let gutter = document.createElement("div");
        gutter.className = "snek-gutter snek-t-" + type;
        wrapper.appendChild(gutter);
        wrapper.appendChild(elem);
        elem.classList.add("snek-result");
        elem.classList.add("snek-t-" + type);
        (target || this.pane).appendChild(wrapper);
        return wrapper;
    }

    setStatus(data) {
        let timestamp = (new Date()).toLocaleTimeString("en-gb");
        this.statusBar.className =
            `snek-status-bar snek-status-${data.type} snek-status-flash-${data.type}`;
        this.statusBar.innerText = `${data.value} -- ${timestamp}`;
        let statusCopy = document.createElement("div");
        statusCopy.innerText = `${timestamp} ${data.value}`;
        this.statusHistory.appendChild(statusCopy);
        setTimeout(
            () => {
                this.statusBar.classList.remove(`snek-status-${data.type}`);
                this.statusBar.classList.add(`snek-status-normal`);
            },
            10000
        );
        setTimeout(
            () => {
                this.statusBar.classList.remove(`snek-status-flash-${data.type}`);
            },
            50
        );
    }

    recv_resource(data) {
        let elem = this.reify(data.value);
        document.head.appendChild(elem);
    }

    recv_result(data) {
        let elem = this.reify(data.value);
        let evalid = !data.evalid ? `E${++evalIdGen}` : data.evalid
        let prbox = document.getElementById("pr-eval-" + evalid);
        if (prbox === null) {
            prbox = document.createElement("div");
            prbox.id = "pr-eval-" + evalid;
            prbox.setAttribute("pinnable", "");
            this.pane.appendChild(prbox);
        }
        if (data.type === "statement") { }
        else {
            this.append(elem, data.type, prbox);
        }
    }

    recv_fill(data) {
        let elem = this.reify(data.value);
        let target = document.getElementById(data.target);
        while (target.firstChild) {
            target.removeChild(target.firstChild);
        }
        target.appendChild(elem);
    }

    recv_insert(data) {
        let elem = this.reify(data.value);
        let target = document.getElementById(data.target);
        if (data.index === undefined || data.index === null) {
            target.appendChild(elem);
        }
        else {
            target.insertBefore(elem, target.children[data.index]);
        }
    }

    recv_clear(data) {
        let target = document.getElementById(data.target);
        while (target.firstChild) {
            target.removeChild(target.firstChild);
        }
    }

    recv_echo(data) {
        let ed = this.read_only_editor(data.value.trimEnd(), data.language || "python");
        let elem = document.createElement("div");
        elem.appendChild(ed);
        this.append(elem, "echo");
    }

    recv_response(data) {
        let {resolve, reject} = this.$responseMap[data.response_id];
        if (data.error) {
            reject(data.error);
        }
        else {
            resolve(data.value);
        }
    }

    recv_pastecode(data) {
        let varname = data.value;
        this.editor.trigger("keyboard", "type", {text: varname});
        this.editor.focus();
    }

    recv_status(data) {
        this.setStatus(data);
    }

    recv_set_nav(data) {
        if (data.navid === undefined || data.navid !== this.last_nav) {
            this.nav.innerHTML = "";
            if (data.value) {
                let elem = this.reify(data.value);
                this.nav.appendChild(elem);
            }
            this.last_nav = data.navid;
        }
    }

    recv_eval(data) {
        eval(data.value);
    }

    recv_set_mode(data) {
        this.inputMode.innerHTML = data.html;
    }

    recv_add_history(data) {
        this.history.push.apply(this.history, data["history"].reverse());
    }

    recv_set_lib(data) {
        for (let key in data.lib) {
            this.lib[key] = this.get_external(data.lib[key]);
        }
    }

    recv_broadcast(data) {
        let selector = `*[channel-${data.key}=""]`
        if (data.subkey) {
            selector = `${selector}, *[channel-${data.key}="${data.subkey}"]`
        }
        for (let element of document.querySelectorAll(selector)) {
            if (element.onbroadcast) {
                element.onbroadcast(data);
            }
        }
    }

    recv_bad(data) {
        console.error("Received an unknown command:", data.command);
    }

    connect() {
        let port = window.location.port;
        let socket = new WebSocket(`ws://localhost:${port}/sktk?session=main`);

        socket.addEventListener('message', event => {
            let data = JSON.parse(event.data);
            this.find_method("recv", data.command, this.recv_bad)(data)
        });

        socket.addEventListener('error', event => {
            this.closed = true;
            this.setStatus({
                type: "error",
                value: "a connection error occurred",
            });
        });

        socket.addEventListener('close', event => {
            this.closed = true;
            this.setStatus({
                type: "normal",
                value: "the connection was closed",
            });
        });

        this.socket = socket;
    }

    getEditor() {
        return editor;
    }

}


let exports = {
    mainRepl,
    Repl,
}

return exports;

});
