
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
define(["vs/editor/editor.main", "Fuse"], (monaco, Fuse) => {

const KM = monaco.KeyMod;
const KC = monaco.KeyCode;

let mainRepl = null;
let evalIdGen = 0;


class FuzzySearchResults {
    constructor(element, entries) {
        this.element = element;
        this.entries = entries;
        this.structured_results = null;
        this.cursors = [0];
        element.className = "snek-fuzzy-search";
        this.results = document.createElement("div");
        this.results.className = "snek-fuzzy-search-results";
        element.appendChild(this.results);
    }

    get() {
        let ret = [];
        for (let cursor of this.cursors) {
            const result = this.structured_results[cursor];
            if (result !== undefined) {
                const entry = result.item;
                ret.unshift(this.entries[entry]);
            }
        }
        return ret.join("\n") || null;
    }

    showResults(results) {
        this.results.innerHTML = "";
        for (const result of results) {
            const row = document.createElement("div");
            row.innerText = this.entries[result.item];
            this.results.appendChild(row);
        }
        if (!this.results.children.length) {
            this.results.innerHTML = "No matches";
        }
        this.structured_results = results;
    }

    updateCursors(new_cursors) {
        const n = this.structured_results.length;
        if (n === 0) {
            return;
        }
        for (let cursor of this.cursors) {
            if (new_cursors.indexOf(cursor) === -1) {
                this.results.children[cursor].classList.remove("snek-fuzzy-cursor");
            }
        }
        for (let cursor of new_cursors) {
            this.results.children[cursor].classList.add("snek-fuzzy-cursor");
        }
        this.cursors = new_cursors;
    }

    setCursor(value) {
        let new_cursors = [value];
        this.updateCursors(new_cursors);
    }

    addCursor(value) {
        let new_cursors = this.cursors.slice(0);
        new_cursors.push(value);
        new_cursors.sort();
        this.updateCursors(new_cursors);
    }

    expandUp() {
        const x = this.cursors.length - 1;
        if (this.cursors.length && this.cursors[x] < this.structured_results.length - 1) {
            this.addCursor(this.cursors[x] + 1);
        }
    }

    expandDown() {
        if (this.cursors.length && this.cursors[0] > 0) {
            this.addCursor(this.cursors[0] - 1);
        }
    }
}


class Repl {

    constructor(target) {
        this.container = target;
        this.options = {};
        this.pane = target.querySelector(".snek-pane");
        this.outerPane = target.querySelector(".snek-outer-pane");
        this.pinpane = target.querySelector(".snek-pin-pane");
        this.inputOuter = target.querySelector(".snek-input-box");
        this.inputBox = target.querySelector(".snek-input");
        this.inputMode = target.querySelector(".snek-input-mode");
        this.statusBar = target.querySelector(".snek-status-bar");
        this.nav = target.querySelector(".snek-nav");
        this._setupEditor(this.inputBox);

        this.historySelection = 0;
        this.filter = null;
        this.filteredHistory = [""];
        this.history = [""];
        this.expectedContent = null;
        this.historyPopup = null;

        target.onclick = this.$globalClickEvent.bind(this);
        window.onkeydown = this.$globalKDEvent.bind(this);
        window.$$SKTK = this.sktk.bind(this);
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
    }

    sktk(id, ...args) {
        // Call a Python function by id
        const exec = async (...args) => {
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

        this.editor.onDidChangeCursorPosition(() => {
            let position = editor.getPosition();
            let lineno = position.lineNumber;
            let total = editor.getModel().getLineCount();
            this.atBeginning.set(lineno == 1);
            this.atEnd.set(lineno == total);
        });

        this.editor.getModel().onDidChangeContent(() => {
            let total = editor.getModel().getLineCount();
            this.multiline.set(
                total > 1
                || editor.getModel().getLineContent(1).match(/[\(\[\{:]$|^@/)
            )
            if (this.historyPopup) {
                this.setupFilter();
            }
            else if (this.expectedContent !== null
                && this.editor.getValue() !== this.expectedContent) {
                    this.filter = null;
                    this.expectedContent = null;
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
            this.destroyHistoryPopup();
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
            KC.Enter,
            () => {
                const selection = this.historyPopup.get();
                if (selection) {
                    this.editor.setValue(selection);
                    let nlines = this.editor.getModel().getLineCount();
                    this.editor.setPosition({lineNumber: nlines, column: 1000000});
                }
                this.destroyHistoryPopup();
            },
            "popupActive"
        );

        editor.addCommand(
            KC.Escape,
            () => this.destroyHistoryPopup(),
            "popupActive"
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
            () => this.setupHistoryPopup()
        );

        editor.addCommand(
            KC.UpArrow,
            () => { this.historyShift(-1); },
            "atBeginning"
        );

        editor.addCommand(
            KC.DownArrow,
            () => { this.historyShift(1); },
            "atEnd"
        );

        editor.addCommand(
            KM.Shift | KC.UpArrow,
            () => { this.historyPopup.expandUp(); },
            "popupActive"
        );

        editor.addCommand(
            KM.Shift | KC.DownArrow,
            () => { this.historyPopup.expandDown(); },
            "popupActive"
        );

        this.editor = editor;
    }

    setupHistoryPopup() {
        const el = document.createElement("div");
        const fuzz = new FuzzySearchResults(
            el,
            this.history.slice(1),
        );
        this.inputOuter.insertBefore(el, this.inputMode);
        this.historyPopup = fuzz;
        this.popupActive.set(true);
        this.setupFilter();
    }

    destroyHistoryPopup() {
        if (this.historyPopup !== null) {
            this.historyPopup.element.remove();
            this.historyPopup = null;
            this.popupActive.set(false);
            this.filter = null;
        }
    }

    setupFilter() {
        const popup = this.historyPopup !== null;
        this.filter = this.editor.getValue();
        this.history[0] = this.filter;
        const histo = popup ? this.history.slice(1) : this.history;
        if (!this.filter) {
            this.filteredHistory = histo.map(
                (elem, idx) => ({item: idx})
            );
        }
        else {
            const options = {
                includeScore: true,
                includeMatches: true,
            };
            const fuse = new Fuse(histo, options);
            this.filteredHistory = fuse.search(this.filter);
        }
        this.historySelection = 0;
        if (popup) {
            this.historyPopup.showResults(this.filteredHistory);
            this.historyPopup.setCursor(0);
        }
    }

    historyShift(delta) {
        if (this.filter === null) {
            this.setupFilter();
        }

        let sel = this.historySelection;
        let n = this.filteredHistory.length;
        let new_sel = Math.max(0, Math.min(n - 1, sel - delta));

        if (new_sel === sel) {
            return;
        }

        this.historySelection = new_sel;
        let item = this.filteredHistory[new_sel].item;

        if (this.historyPopup !== null) {
            this.historyPopup.setCursor(new_sel);
        }
        else {
            let text = this.history[item];

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

    send(message) {
        // Send a message back to SnekTalk
        if (this.closed) {
            this.setStatus({
                type: "error",
                value: "operation failed because the connection is closed",
            });
        }
        else {
            this.socket.send(JSON.stringify(message));
        }
    }

    append(elem, type) {
        let wrapper = document.createElement("div");
        wrapper.className = "snek-line snek-t-" + type;
        let gutter = document.createElement("div");
        gutter.className = "snek-gutter snek-t-" + type;
        wrapper.appendChild(gutter);
        wrapper.appendChild(elem);
        elem.className = "snek-result snek-t-" + type;
        this.pane.appendChild(wrapper);
        return wrapper;
    }

    setStatus(data) {
        let timestamp = (new Date()).toLocaleTimeString("en-gb");
        this.statusBar.className =
            `snek-status-bar snek-status-${data.type} snek-status-flash-${data.type}`;
        this.statusBar.innerText = `${data.value} -- ${timestamp}`;
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

    process_message(data) {
        if (data.command == "resource") {
            let elem = this.reify(data.value);
            document.head.appendChild(elem);
        }
        else if (data.command == "result") {
            let elem = this.reify(data.value);
            let evalid = !data.evalid ? `E${++evalIdGen}` : data.evalid
            let prbox = document.getElementById("pr-eval-" + evalid);
            if (prbox === null) {
                prbox = document.createElement("div");
                prbox.id = "pr-eval-" + evalid;
                this.append(prbox, "print");
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
            let ed = this.read_only_editor(data.value.trimEnd(), data.language || "python");
            let elem = document.createElement("div");
            elem.appendChild(ed);
            this.append(elem, "echo");
        }
        else if (data.command == "response") {
            let {resolve, reject} = this.$responseMap[data.response_id];
            if (data.error) {
                reject(data.error);
            }
            else {
                resolve(data.value);
            }
        }
        else if (data.command == "pastevar") {
            let varname = data.value;
            this.editor.trigger("keyboard", "type", {text: varname});
            this.editor.focus();
        }
        else if (data.command == "status") {
            this.setStatus(data);
        }
        else if (data.command == "set_nav") {
            this.nav.innerHTML = "";
            if (data.value) {
                let elem = this.reify(data.value);
                this.nav.appendChild(elem);
            }
        }
        else if (data.command == "eval") {
            eval(data.value);
        }
        else if (data.command == "set_mode") {
            this.inputMode.innerHTML = data.html;
        }
        else {
            console.error("Received an unknown command:", data.command);
        }
    }

    connect() {
        let port = window.location.port;
        let socket = new WebSocket(`ws://localhost:${port}/sktk?session=main`);

        socket.addEventListener('message', event => {
            let data = JSON.parse(event.data);
            this.process_message(data);
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
