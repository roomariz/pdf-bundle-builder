from __future__ import annotations

import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from pdf_merger.merge_pdfs import clean_title, get_prefix_number, merge_pdfs

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


class PDFBundleBuilderApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        self.title("PDF Bundle Builder")
        self.geometry("760x520")

        self.input_folder = Path.cwd() / "input"

        self.heading = ctk.CTkLabel(
            self,
            text="PDF Bundle Builder",
            font=("Arial", 24, "bold"),
        )
        self.heading.pack(pady=(25, 5))

        self.subtitle = ctk.CTkLabel(
            self,
            text="Select a folder containing numbered PDF files and generate one merged bundle.",
            font=("Arial", 13),
        )
        self.subtitle.pack(pady=(0, 20))

        self.folder_label = ctk.CTkLabel(
            self,
            text=f"Input folder: {self.input_folder}",
            wraplength=680,
        )
        self.folder_label.pack(pady=5)

        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(pady=10)

        self.select_button = ctk.CTkButton(
            button_frame,
            text="Select Input Folder",
            command=self.select_folder,
            width=180,
        )
        self.select_button.grid(row=0, column=0, padx=8)

        self.refresh_button = ctk.CTkButton(
            button_frame,
            text="Refresh List",
            command=self.load_pdf_list,
            width=140,
        )
        self.refresh_button.grid(row=0, column=1, padx=8)

        self.merge_button = ctk.CTkButton(
            button_frame,
            text="Generate Merged PDF",
            command=self.generate_pdf,
            width=180,
        )
        self.merge_button.grid(row=0, column=2, padx=8)

        self.open_output_button = ctk.CTkButton(
            button_frame,
            text="Open Output Folder",
            command=self.open_last_output_folder,
            width=180,
            state="disabled",
        )
        self.open_output_button.grid(row=0, column=3, padx=8)

        self.listbox = tk.Listbox(self, width=95, height=15)
        self.listbox.pack(padx=25, pady=15, fill="both", expand=True)

        self.status_label = ctk.CTkLabel(self, text="")
        self.status_label.pack(pady=(0, 15))

        self._worker_thread: threading.Thread | None = None
        self._progress_queue: queue.Queue[str] = queue.Queue()
        self._last_output_dir: Path | None = None

        self.load_pdf_list()

    def _set_controls_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.select_button.configure(state=state)
        self.refresh_button.configure(state=state)
        self.merge_button.configure(state=state)

    def _set_status(self, message: str) -> None:
        self.status_label.configure(text=message)

    def _set_empty_state(self, message: str) -> None:
        self.listbox.delete(0, tk.END)
        self.listbox.insert(tk.END, message)
        self._set_status(message)
        self.merge_button.configure(state="disabled")

    def select_folder(self) -> None:
        folder = filedialog.askdirectory(
            title="Select folder containing PDFs",
            initialdir=str(self.input_folder) if self.input_folder.exists() else None,
        )

        if folder:
            self.input_folder = Path(folder)
            self.folder_label.configure(text=f"Input folder: {self.input_folder}")
            self.load_pdf_list()

    def _validate_input_folder(self) -> list[Path]:
        if not self.input_folder.exists():
            raise FileNotFoundError(f"Input folder does not exist:\n{self.input_folder}")
        if not self.input_folder.is_dir():
            raise NotADirectoryError(f"Input path is not a folder:\n{self.input_folder}")

        pdf_files = list(self.input_folder.glob("*.pdf"))
        if not pdf_files:
            raise FileNotFoundError(f"No PDF files found in:\n{self.input_folder}")

        prefixes_to_files: dict[int, list[Path]] = {}
        for pdf_file in pdf_files:
            prefix = get_prefix_number(pdf_file)
            prefixes_to_files.setdefault(prefix, []).append(pdf_file)

        duplicates = {k: v for k, v in prefixes_to_files.items() if len(v) > 1}
        if duplicates:
            parts: list[str] = ["Duplicate numeric prefixes detected:"]
            for prefix in sorted(duplicates):
                names = ", ".join(sorted(p.name for p in duplicates[prefix]))
                parts.append(f"- {prefix}: {names}")
            raise ValueError("\n".join(parts))

        return sorted(pdf_files, key=get_prefix_number)

    def load_pdf_list(self) -> None:
        self.open_output_button.configure(state="disabled")
        self._last_output_dir = None

        try:
            ordered_files = self._validate_input_folder()
        except FileNotFoundError:
            self._set_empty_state(
                "No input PDFs yet. Click “Select Input Folder” and choose a folder with numbered PDFs (e.g. 01.Passport.pdf)."
            )
            return
        except (NotADirectoryError, ValueError) as error:
            self._set_empty_state(str(error))
            return

        self.listbox.delete(0, tk.END)

        for file in ordered_files:
            number = get_prefix_number(file)
            title = clean_title(file)
            self.listbox.insert(tk.END, f"{number:02}. {title}  —  {file.name}")

        self.merge_button.configure(state="normal")
        self._set_status(f"Ready: {len(ordered_files)} PDF file(s).")

    def _poll_progress(self) -> None:
        latest: str | None = None
        while True:
            try:
                latest = self._progress_queue.get_nowait()
            except queue.Empty:
                break

        if latest is not None:
            self._set_status(latest)

        if self._worker_thread and self._worker_thread.is_alive():
            self.after(100, self._poll_progress)
        else:
            self._set_controls_enabled(True)

    def open_last_output_folder(self) -> None:
        if self._last_output_dir is None:
            return
        self.open_folder(self._last_output_dir)

    def generate_pdf(self) -> None:
        try:
            if self._worker_thread and self._worker_thread.is_alive():
                messagebox.showinfo("Busy", "A merge is already running.")
                return

            try:
                self._validate_input_folder()
            except FileNotFoundError as error:
                messagebox.showerror("No PDFs Found", str(error))
                self.load_pdf_list()
                return
            except NotADirectoryError as error:
                messagebox.showerror("Invalid Folder", str(error))
                self.load_pdf_list()
                return
            except ValueError as error:
                messagebox.showerror("Fix Filenames", str(error))
                self.load_pdf_list()
                return

            save_path = filedialog.asksaveasfilename(
                title="Save merged PDF as",
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf")],
                initialfile="merged_documents_final.pdf",
            )

            if not save_path:
                return

            output_path = Path(save_path)
            if output_path.exists():
                overwrite = messagebox.askyesno(
                    "Overwrite File?",
                    f"The file already exists:\n\n{output_path}\n\nOverwrite it?",
                )
                if not overwrite:
                    return

            self._set_controls_enabled(False)
            self.open_output_button.configure(state="disabled")
            self._last_output_dir = None
            self._set_status("Starting merge…")
            self.update_idletasks()

            def run_merge() -> None:
                try:
                    final_output = merge_pdfs(
                        input_dir=self.input_folder,
                        output_file=output_path,
                        progress_callback=self._progress_queue.put,
                    )
                except Exception as error:  # noqa: BLE001
                    self._progress_queue.put(f"Error: {error}")
                    error_message = str(error)
                    self.after(0, lambda: messagebox.showerror("Error", error_message))
                    return

                self._last_output_dir = final_output.parent
                self._progress_queue.put(f"Done. Saved to: {final_output}")
                self.after(
                    0,
                    lambda: messagebox.showinfo(
                        "Success",
                        f"Merged PDF created successfully.\n\nSaved at:\n{final_output}",
                    ),
                )
                self.after(0, lambda: self.open_output_button.configure(state="normal"))

            self._worker_thread = threading.Thread(target=run_merge, daemon=True)
            self._worker_thread.start()
            self.after(100, self._poll_progress)

        except Exception as error:  # noqa: BLE001
            messagebox.showerror("Error", str(error))

    @staticmethod
    def open_folder(folder: Path) -> None:
        if sys.platform.startswith("win"):
            subprocess.Popen(["explorer", str(folder)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(folder)])
        else:
            subprocess.Popen(["xdg-open", str(folder)])


if __name__ == "__main__":
    app = PDFBundleBuilderApp()
    app.mainloop()
