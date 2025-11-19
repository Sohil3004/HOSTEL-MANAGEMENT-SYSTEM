 1. Project Title & Description

Hostel Management System

Built using MySQL (DBMS) + Python Gradio (Frontend)

2. Features / Functionalities

Student Management (Add/Update/Delete)

Room Management with automatic occupancy updates

Fee Payment + Auto Fee Status Update (Trigger)

Complaint Management (Raise + View complaints)

Role-Based Login (Admin / Staff / Student)

Dashboard summary

View tables (Staff/Room/Student/Fee/Complaint)

3. Tech Stack

Frontend: Python, Gradio

Database: MySQL

Library: mysql-connector-python

4. DDL Commands Included

CREATE TABLE Staff

CREATE TABLE Room

CREATE TABLE Student

CREATE TABLE Complaint

CREATE TABLE Fee_Payment

Indexes + Constraints + CHECK

5. Triggers Implemented

Update fee status after payment

Prevent assigning full rooms

Increment occupancy after adding student

Validate update to new room

Adjust counts when room changes

Decrement occupancy on delete

6. Stored Procedures

ViewStudentDetails(student_id)

RaiseComplaint(student_id, text)

7. Functions

GetRoomOccupancy(room_id)

CalculatePendingFees()

8. CRUD Operations Provided

Add student

Update student

Delete student

Add fee payment

Raise complaint

View tables

9. SQL Concepts Used

JOIN

Aggregate functions

Nested queries

CHECK constraints

Foreign keys

Stored procedures/functions

Triggers

10. How to Run

Import SQL file

Install Python dependencies

Run Python Gradio UI

Visit localhost link