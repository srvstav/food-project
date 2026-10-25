USE mess;

INSERT INTO messes (id, name) VALUES (1, 'BluDove'), (2, 'BluSpring');

INSERT INTO meal_slots (id, code, name, starts_at, ends_at) VALUES
  (1, 'breakfast', 'Breakfast', '07:30', '09:30'),
  (2, 'lunch',     'Lunch',     '12:30', '14:30'),
  (3, 'hitea',     'Hi-Tea',    '17:00', '18:00'),
  (4, 'dinner',    'Dinner',    '19:30', '21:30');

INSERT INTO menu_items (mess_id, slot_id, dish) VALUES
  -- BluDove
  (1, 1, 'Aloo Paratha'), (1, 1, 'Curd'), (1, 1, 'Masala Chai'), (1, 1, 'Banana'),
  (1, 2, 'Rajma'), (1, 2, 'Jeera Rice'), (1, 2, 'Tawa Roti'), (1, 2, 'Boondi Raita'), (1, 2, 'Salad'),
  (1, 3, 'Samosa'), (1, 3, 'Green Chutney'), (1, 3, 'Masala Chai'),
  (1, 4, 'Paneer Butter Masala'), (1, 4, 'Dal Tadka'), (1, 4, 'Butter Naan'), (1, 4, 'Steamed Rice'), (1, 4, 'Gulab Jamun'),
  -- BluSpring
  (2, 1, 'Poha'), (2, 1, 'Boiled Eggs'), (2, 1, 'Bread Butter Jam'), (2, 1, 'Cold Coffee'),
  (2, 2, 'Chole'), (2, 2, 'Bhature'), (2, 2, 'Veg Pulao'), (2, 2, 'Lassi'),
  (2, 3, 'Veg Sandwich'), (2, 3, 'Bhel Puri'), (2, 3, 'Lemon Tea'),
  (2, 4, 'Dal Baati Churma'), (2, 4, 'Gatte ki Sabzi'), (2, 4, 'Chapati'), (2, 4, 'Kheer');

-- Sample NGOs near campus. Fictional names and numbers, for the demo only.
INSERT INTO ngos (name, area, contact_phone) VALUES
  ('Sahyog Food Shelf',       'Bagru',        '9000000001'),
  ('Ann Seva Night Shelter',  'Sanganer',     '9000000002'),
  ('Dahmi Community Kitchen', 'Dahmi Kalan',  '9000000003');
