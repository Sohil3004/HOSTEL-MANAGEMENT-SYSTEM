-- ===========================================================
--  CLEAN REBUILD (Safe to run on fresh schema)
-- ===========================================================
CREATE DATABASE IF NOT EXISTS college_dorm;
USE college_dorm;
-- ===========================================================
--  TABLE: STAFF
-- ===========================================================
CREATE TABLE Staff (
    Staff_ID INT AUTO_INCREMENT PRIMARY KEY,
    Staff_Name VARCHAR(100) NOT NULL,
    Role ENUM('Warden', 'Accountant', 'Cleaner', 'Security', 'Other') DEFAULT 'Other',
    Contact_Number VARCHAR(15),
    Email VARCHAR(100) UNIQUE,
    Joining_Date DATE DEFAULT (CURRENT_DATE),
    Salary DECIMAL(10,2) DEFAULT 0.00
) ENGINE=InnoDB;

-- ===========================================================
--  TABLE: ROOM  (start occupancy at 0; add a CHECK)
-- ===========================================================
CREATE TABLE Room (
    Room_ID INT AUTO_INCREMENT PRIMARY KEY,
    Block_Name VARCHAR(10),
    Room_No VARCHAR(10),
    Capacity INT NOT NULL,
    Current_Occupancy INT NOT NULL DEFAULT 0,
    CONSTRAINT chk_room_occ_bounds CHECK (
        Current_Occupancy >= 0 AND Current_Occupancy <= Capacity
    )
) ENGINE=InnoDB;

-- Indices that help joins/lookups
CREATE INDEX idx_room_block_no ON Room(Block_Name, Room_No);

-- ===========================================================
--  TABLE: STUDENT
-- ===========================================================
CREATE TABLE Student (
    Student_ID INT AUTO_INCREMENT PRIMARY KEY,
    Name VARCHAR(100) NOT NULL,
    Gender ENUM('Male', 'Female', 'Other') NOT NULL,
    Department VARCHAR(50),
    Room_ID INT NULL,
    Fee_Status ENUM('Paid', 'Pending') DEFAULT 'Pending',
    CONSTRAINT fk_room FOREIGN KEY (Room_ID) REFERENCES Room(Room_ID)
        ON UPDATE RESTRICT
        ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE INDEX idx_student_room ON Student(Room_ID);
CREATE INDEX idx_student_fee ON Student(Fee_Status);

-- ===========================================================
--  TABLE: COMPLAINT
-- ===========================================================
CREATE TABLE Complaint (
    Complaint_ID INT AUTO_INCREMENT PRIMARY KEY,
    Student_ID INT,
    Complaint_Text TEXT NOT NULL,
    Complaint_Date DATETIME DEFAULT CURRENT_TIMESTAMP,
    Status ENUM('Open', 'In Progress', 'Resolved') DEFAULT 'Open',
    CONSTRAINT fk_compl_student FOREIGN KEY (Student_ID) REFERENCES Student(Student_ID)
        ON UPDATE RESTRICT
        ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE INDEX idx_complaint_student ON Complaint(Student_ID);
CREATE INDEX idx_complaint_status ON Complaint(Status);

-- ===========================================================
--  TABLE: FEE_PAYMENT
-- ===========================================================
CREATE TABLE Fee_Payment (
    Payment_ID INT AUTO_INCREMENT PRIMARY KEY,
    Student_ID INT,
    Amount DECIMAL(10,2),
    Payment_Date DATE DEFAULT (CURRENT_DATE),
    Payment_Mode ENUM('Cash', 'Card', 'UPI', 'Bank Transfer'),
    Staff_ID INT,
    CONSTRAINT fk_fee_student FOREIGN KEY (Student_ID) REFERENCES Student(Student_ID)
        ON UPDATE RESTRICT
        ON DELETE SET NULL,
    CONSTRAINT fk_fee_staff FOREIGN KEY (Staff_ID) REFERENCES Staff(Staff_ID)
        ON UPDATE RESTRICT
        ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE INDEX idx_fee_student ON Fee_Payment(Student_ID);
CREATE INDEX idx_fee_staff ON Fee_Payment(Staff_ID);

-- ===========================================================
--  FUNCTIONS
-- ===========================================================
DELIMITER //
CREATE FUNCTION GetRoomOccupancy(room_id INT)
RETURNS INT
DETERMINISTIC
BEGIN
    DECLARE occ INT DEFAULT NULL;
    SELECT Current_Occupancy INTO occ FROM Room WHERE Room_ID = room_id LIMIT 1;
    RETURN COALESCE(occ, 0);
END;
//
DELIMITER ;

DELIMITER //
CREATE FUNCTION CalculatePendingFees()
RETURNS INT
DETERMINISTIC
BEGIN
    DECLARE total_pending INT;
    SELECT COUNT(*) INTO total_pending FROM Student WHERE Fee_Status = 'Pending';
    RETURN COALESCE(total_pending, 0);
END;
//
DELIMITER ;

-- ===========================================================
--  STORED PROCEDURES
-- ===========================================================
DELIMITER //
CREATE PROCEDURE ViewStudentDetails(IN stud_id INT)
BEGIN
    SELECT 
        s.Student_ID,
        s.Name,
        s.Department,
        s.Fee_Status,
        r.Room_No,
        r.Block_Name
    FROM Student s
    LEFT JOIN Room r ON s.Room_ID = r.Room_ID
    WHERE s.Student_ID = stud_id;
END;
//
DELIMITER ;

DELIMITER //
CREATE PROCEDURE RaiseComplaint(IN stud_id INT, IN text TEXT)
BEGIN
    INSERT INTO Complaint (Student_ID, Complaint_Text) 
    VALUES (stud_id, text);
END;
//
DELIMITER ;

-- ===========================================================
--  TRIGGERS
--  Fee status auto-update on payment
-- ===========================================================
DELIMITER //
CREATE TRIGGER trg_update_fee_status
AFTER INSERT ON Fee_Payment
FOR EACH ROW
BEGIN
    UPDATE Student
    SET Fee_Status = 'Paid'
    WHERE Student_ID = NEW.Student_ID;
END;
//
DELIMITER ;

-- 1) BEFORE INSERT: prevent assignment to full rooms
DELIMITER //
CREATE TRIGGER trg_room_before_insert_student
BEFORE INSERT ON Student
FOR EACH ROW
BEGIN
    IF NEW.Room_ID IS NOT NULL THEN
        IF (SELECT Current_Occupancy FROM Room WHERE Room_ID = NEW.Room_ID) 
           >= (SELECT Capacity FROM Room WHERE Room_ID = NEW.Room_ID) THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Room is full: cannot assign student.';
        END IF;
    END IF;
END;
//
DELIMITER ;

-- 2) AFTER INSERT: increment room occupancy
DELIMITER //
CREATE TRIGGER trg_room_after_insert_student
AFTER INSERT ON Student
FOR EACH ROW
BEGIN
    IF NEW.Room_ID IS NOT NULL THEN
        UPDATE Room
        SET Current_Occupancy = Current_Occupancy + 1
        WHERE Room_ID = NEW.Room_ID;
    END IF;
END;
//
DELIMITER ;

-- 3) BEFORE UPDATE: prevent moving into full rooms
DELIMITER //
CREATE TRIGGER trg_room_before_update_student
BEFORE UPDATE ON Student
FOR EACH ROW
BEGIN
    IF NEW.Room_ID IS NULL THEN
        LEAVE trg_room_before_update_student;
    END IF;

    IF (OLD.Room_ID IS NULL OR NEW.Room_ID <> OLD.Room_ID) THEN
        IF (SELECT Current_Occupancy FROM Room WHERE Room_ID = NEW.Room_ID) 
           >= (SELECT Capacity FROM Room WHERE Room_ID = NEW.Room_ID) THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Target room is full: cannot move student.';
        END IF;
    END IF;
END;
//
DELIMITER ;

-- 4) AFTER UPDATE: adjust counters when room changes
DELIMITER //
CREATE TRIGGER trg_room_after_update_student
AFTER UPDATE ON Student
FOR EACH ROW
BEGIN
    IF (OLD.Room_ID IS NOT NULL AND NEW.Room_ID IS NULL) THEN
        -- moved out of room: decrement old
        UPDATE Room
        SET Current_Occupancy = CASE
            WHEN Current_Occupancy > 0 THEN Current_Occupancy - 1 ELSE 0 END
        WHERE Room_ID = OLD.Room_ID;
    ELSEIF (OLD.Room_ID IS NULL AND NEW.Room_ID IS NOT NULL) THEN
        -- moved from no room to a room: increment new
        UPDATE Room
        SET Current_Occupancy = Current_Occupancy + 1
        WHERE Room_ID = NEW.Room_ID;
    ELSEIF (OLD.Room_ID IS NOT NULL AND NEW.Room_ID IS NOT NULL AND OLD.Room_ID <> NEW.Room_ID) THEN
        -- moved between rooms: dec old, inc new
        UPDATE Room
        SET Current_Occupancy = CASE
            WHEN Current_Occupancy > 0 THEN Current_Occupancy - 1 ELSE 0 END
        WHERE Room_ID = OLD.Room_ID;

        UPDATE Room
        SET Current_Occupancy = Current_Occupancy + 1
        WHERE Room_ID = NEW.Room_ID;
    END IF;
END;
//
DELIMITER ;

-- 5) AFTER DELETE: decrement old room, never below 0
DELIMITER //
CREATE TRIGGER trg_decrease_room_occupancy
AFTER DELETE ON Student
FOR EACH ROW
BEGIN
    IF OLD.Room_ID IS NOT NULL THEN
        UPDATE Room
        SET Current_Occupancy = CASE
            WHEN Current_Occupancy > 0 THEN Current_Occupancy - 1 ELSE 0 END
        WHERE Room_ID = OLD.Room_ID;
    END IF;
END;
//
DELIMITER ;

-- ===========================================================
--  SAMPLE DATA (Rooms start with occupancy = 0)
-- ===========================================================
INSERT INTO Room (Block_Name, Room_No, Capacity, Current_Occupancy) VALUES
('A', 'A-101', 3, 0),
('A', 'A-102', 2, 0),
('B', 'B-201', 4, 0),
('B', 'B-202', 3, 0);

INSERT INTO Staff (Staff_Name, Role, Contact_Number, Email, Salary)
VALUES 
('Ravi Kumar', 'Warden', '9876543210', 'ravi.k@college.com', 40000.00),
('Priya Sharma', 'Accountant', '9988776655', 'priya.s@college.com', 35000.00);

-- Insert students (triggers will increment room occupancy accordingly)
INSERT INTO Student (Name, Gender, Department, Room_ID, Fee_Status) VALUES
('Aarav Mehta', 'Male', 'CSE', 1, 'Pending'),
('Diya Sharma', 'Female', 'ECE', 2, 'Paid'),
('Rohit Patel', 'Male', 'Mechanical', 3, 'Pending'),
('Neha Reddy', 'Female', 'IT', 1, 'Pending');

-- Payments (fee trigger will mark corresponding students as Paid)
INSERT INTO Fee_Payment (Student_ID, Amount, Payment_Date, Payment_Mode, Staff_ID)
VALUES 
(1, 25000, '2025-10-30', 'UPI', 2),
(3, 26000, '2025-11-01', 'Card', 2);

-- Optional: sample complaint
INSERT INTO Complaint (Student_ID, Complaint_Text, Status)
VALUES (1, 'Fan not working in my room', 'Open');

-- ===========================================================
--  VERIFICATION QUERIES
-- ===========================================================
-- Room occupancy should reflect the number of students in each room
SELECT Room_ID, Block_Name, Room_No, Capacity, Current_Occupancy FROM Room ORDER BY Room_ID;

-- Fee status auto-updates
SELECT Student_ID, Name, Fee_Status FROM Student ORDER BY Student_ID;

-- Functions
SELECT GetRoomOccupancy(1) AS Occ_Room_1;
SELECT CalculatePendingFees() AS Pending_Fees_Count;

-- Procedure checks
CALL ViewStudentDetails(1);
CALL RaiseComplaint(2, 'Leaking faucet in bathroom');