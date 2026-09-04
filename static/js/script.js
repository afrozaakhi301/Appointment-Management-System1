document.addEventListener("DOMContentLoaded", function () {
    // 1. Automatically set minimum date on date picker inputs to today's date
    const today = new Date().toISOString().split("T")[0];
    document.querySelectorAll("input[type='date']").forEach(function (input) {
        if (!input.getAttribute("min") && !input.classList.contains("allow-past-date")) {
            input.setAttribute("min", today);
        }
    });

    // 2. Dynamic schedule helper on booking and rescheduling pages
    const engineerSelect = document.getElementById("id_engineer");
    const dateInput = document.getElementById("id_appointment_date");
    const startTimeInput = document.getElementById("id_start_time");
    const endTimeInput = document.getElementById("id_end_time");
    const scheduleHelpBox = document.getElementById("schedule-availability-info");

    let currentScheduleData = null;

    window.selectSuggestedTime = function (start, end) {
        if (startTimeInput && endTimeInput) {
            startTimeInput.value = start;
            endTimeInput.value = end;

            // Trigger change events for validation
            startTimeInput.dispatchEvent(new Event("change"));
            endTimeInput.dispatchEvent(new Event("change"));

            // Highlight active suggested slot button
            document.querySelectorAll(".suggested-slot-btn").forEach(btn => {
                if (btn.getAttribute("data-start") === start && btn.getAttribute("data-end") === end) {
                    btn.classList.remove("btn-outline-primary", "btn-outline-success");
                    btn.classList.add("btn-primary", "text-white", "fw-bold");
                } else {
                    btn.classList.remove("btn-primary", "text-white", "fw-bold");
                    btn.classList.add("btn-outline-primary");
                }
            });

            validateClientSelectedTime();
        }
    };

    function validateClientSelectedTime() {
        if (!currentScheduleData || currentScheduleData.status !== "available") return;
        if (!startTimeInput || !endTimeInput) return;

        const startVal = startTimeInput.value;
        const endVal = endTimeInput.value;
        if (!startVal || !endVal) return;

        const workingSlots = currentScheduleData.working_slots || [];
        const bookedSlots = currentScheduleData.booked_slots || [];

        // Check if inside any working slot
        let insideWorkingHours = false;
        for (let slot of workingSlots) {
            if (startVal >= slot.start && endVal <= slot.end && startVal < endVal) {
                insideWorkingHours = true;
                break;
            }
        }

        // Check booked conflict
        let conflict = false;
        for (let b of bookedSlots) {
            if (startVal < b.end && endVal > b.start) {
                conflict = true;
                break;
            }
        }

        const warningContainer = document.getElementById("time-slot-warning-box");
        if (!warningContainer) return;

        if (!insideWorkingHours) {
            const workingHoursStr = workingSlots.map(s => `${s.start} - ${s.end}`).join(", ");
            warningContainer.classList.remove("d-none");
            warningContainer.className = "alert alert-warning py-2 small mb-2 border-warning";
            warningContainer.innerHTML = `
                <div class="fw-semibold"><i class="bi bi-exclamation-triangle-fill text-warning me-1"></i> Selected time (${startVal} - ${endVal}) is outside the engineer's working availability (${workingHoursStr}).</div>
                <div class="mt-1">Please pick one of the suggested available times below:</div>
            `;
        } else if (conflict) {
            warningContainer.classList.remove("d-none");
            warningContainer.className = "alert alert-danger py-2 small mb-2 border-danger";
            warningContainer.innerHTML = `
                <div class="fw-semibold"><i class="bi bi-x-octagon-fill text-danger me-1"></i> Selected time (${startVal} - ${endVal}) conflicts with an already booked consultation.</div>
                <div class="mt-1">Please select an alternative available slot below:</div>
            `;
        } else {
            warningContainer.classList.remove("d-none");
            warningContainer.className = "alert alert-success py-2 small mb-2 border-success";
            warningContainer.innerHTML = `
                <div class="fw-semibold"><i class="bi bi-check-circle-fill text-success me-1"></i> Perfect! Selected slot (${startVal} - ${endVal}) is within working availability.</div>
            `;
        }
    }

    function checkEngineerSchedule() {
        if (!engineerSelect || !dateInput || !scheduleHelpBox) return;

        const engineerId = engineerSelect.value;
        const dateVal = dateInput.value;

        if (!engineerId || !dateVal) {
            scheduleHelpBox.innerHTML = "";
            scheduleHelpBox.classList.add("d-none");
            currentScheduleData = null;
            return;
        }

        scheduleHelpBox.classList.remove("d-none");
        scheduleHelpBox.innerHTML = `
            <div class="alert alert-info py-2 small mb-0 d-flex align-items-center">
                <span class="spinner-border spinner-border-sm me-2" role="status"></span>
                Checking engineer availability and calculating suggested times...
            </div>
        `;

        fetch(`/scheduling/api/check/${engineerId}/?date=${dateVal}`)
            .then(res => res.json())
            .then(data => {
                currentScheduleData = data;

                if (data.status === "on_leave") {
                    scheduleHelpBox.innerHTML = `
                        <div class="alert alert-danger py-3 small mb-0 shadow-sm border-danger">
                            <div class="fw-bold fs-6 mb-1 text-danger">
                                <i class="bi bi-calendar-x-fill me-1"></i> Engineer On Leave
                            </div>
                            <div>${data.message}</div>
                            ${data.leave_end ? `<div class="mt-2 text-dark"><strong>Suggestion:</strong> Please select an available date starting from <span class="badge bg-danger">${data.leave_end}</span>.</div>` : ''}
                        </div>
                    `;
                } else if (data.status === "not_available") {
                    let weeklyHtml = "";
                    if (data.weekly_schedule && data.weekly_schedule.length > 0) {
                        weeklyHtml = `
                            <div class="mt-2 pt-2 border-top border-warning-subtle">
                                <strong>Suggested Working Days:</strong>
                                <div class="d-flex flex-wrap gap-1 mt-1">
                                    ${data.weekly_schedule.map(w => `<span class="badge bg-warning text-dark border">${w.label}</span>`).join(" ")}
                                </div>
                            </div>
                        `;
                    }
                    scheduleHelpBox.innerHTML = `
                        <div class="alert alert-warning py-3 small mb-0 shadow-sm border-warning">
                            <div class="fw-bold fs-6 mb-1 text-dark">
                                <i class="bi bi-clock-history me-1 text-warning"></i> Engineer Not Available on this Day
                            </div>
                            <div>${data.message}</div>
                            ${weeklyHtml}
                        </div>
                    `;
                } else if (data.status === "available") {
                    let workingSlotsBadges = (data.working_slots || []).map(s => `<span class="badge bg-primary me-1 px-2 py-1"><i class="bi bi-clock me-1"></i>${s.label || s.start + ' - ' + s.end}</span>`).join(" ");
                    
                    let suggestedButtons = "";
                    if (data.suggested_slots && data.suggested_slots.length > 0) {
                        suggestedButtons = `
                            <div class="mt-2 pt-2 border-top border-success-subtle">
                                <div class="fw-semibold text-dark mb-2">
                                    <i class="bi bi-lightning-charge-fill text-warning me-1"></i>Suggested Available Times (Click to Auto-Fill):
                                </div>
                                <div class="d-flex flex-wrap gap-2" id="suggestedSlotsContainer">
                                    ${data.suggested_slots.map(slot => `
                                        <button type="button" 
                                                class="btn btn-sm btn-outline-primary suggested-slot-btn py-1 px-2 rounded-pill shadow-xs" 
                                                data-start="${slot.start}" 
                                                data-end="${slot.end}" 
                                                onclick="selectSuggestedTime('${slot.start}', '${slot.end}')">
                                            <i class="bi bi-calendar-check me-1"></i>${slot.label}
                                        </button>
                                    `).join("")}
                                </div>
                            </div>
                        `;
                    } else {
                        suggestedButtons = `
                            <div class="mt-2 text-danger small">
                                <i class="bi bi-exclamation-circle me-1"></i> All standard 1-hour slots are currently booked for this day. Please choose another date or custom time.
                            </div>
                        `;
                    }

                    let bookedHtml = "";
                    if (data.booked_slots && data.booked_slots.length > 0) {
                        bookedHtml = `
                            <div class="mt-2 small text-muted">
                                <i class="bi bi-lock-fill text-secondary me-1"></i> <strong>Booked Slots:</strong> 
                                ${data.booked_slots.map(b => `<span class="badge bg-secondary-subtle text-secondary border me-1">${b.start} - ${b.end}</span>`).join(" ")}
                            </div>
                        `;
                    }

                    scheduleHelpBox.innerHTML = `
                        <div class="alert alert-success py-3 small mb-0 shadow-sm border-success">
                            <div id="time-slot-warning-box" class="d-none"></div>
                            <div class="d-flex align-items-center justify-content-between flex-wrap gap-2">
                                <div>
                                    <i class="bi bi-check-circle-fill text-success me-1 fs-6"></i> 
                                    <strong class="text-dark">Working Hours (${data.day_name}):</strong> ${workingSlotsBadges}
                                </div>
                            </div>
                            ${bookedHtml}
                            ${suggestedButtons}
                        </div>
                    `;

                    // Check if current inputs are already populated
                    validateClientSelectedTime();
                } else if (data.error) {
                    scheduleHelpBox.innerHTML = `
                        <div class="alert alert-secondary py-2 small mb-0">${data.error}</div>
                    `;
                }
            })
            .catch(err => {
                console.error("Schedule check error:", err);
                scheduleHelpBox.classList.add("d-none");
            });
    }

    if (engineerSelect) {
        engineerSelect.addEventListener("change", checkEngineerSchedule);
    }
    if (dateInput) {
        dateInput.addEventListener("change", checkEngineerSchedule);
        // Initial check if values exist on load
        if (engineerSelect && engineerSelect.value && dateInput.value) {
            checkEngineerSchedule();
        }
    }
    if (startTimeInput) {
        startTimeInput.addEventListener("input", validateClientSelectedTime);
        startTimeInput.addEventListener("change", validateClientSelectedTime);
    }
    if (endTimeInput) {
        endTimeInput.addEventListener("input", validateClientSelectedTime);
        endTimeInput.addEventListener("change", validateClientSelectedTime);
    }
});
