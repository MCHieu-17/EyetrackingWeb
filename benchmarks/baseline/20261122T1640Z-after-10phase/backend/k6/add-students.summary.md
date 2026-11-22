# k6 summary

scenario: add_students

- iterations: count=10.000, rate=4.323
- vus: min=1.000, max=1.000
- http_req_duration: p(90)=42.731, p(95)=52.100, p(99)=59.596, avg=30.123, min=8.883, med=28.538, max=61.470
- http_req_blocked: max=0.193, p(90)=0.030, p(95)=0.112, p(99)=0.177, avg=0.029, min=0.004, med=0.011
- http_req_receiving: p(90)=0.115, p(95)=0.294, p(99)=0.436, avg=0.089, min=0.034, med=0.043, max=0.472
- http_req_failed: rate=0.000
- http_req_connecting: p(99)=0.125, avg=0.014, min=0.000, med=0.000, max=0.137, p(90)=0.014, p(95)=0.076
- http_req_sending: med=0.195, max=0.236, p(90)=0.233, p(95)=0.234, p(99)=0.235, avg=0.179, min=0.081
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_duration{expected_response:true}: avg=30.123, min=8.883, med=28.538, max=61.470, p(90)=42.731, p(95)=52.100, p(99)=59.596
- http_req_waiting: max=61.213, p(90)=42.159, p(95)=51.686, p(99)=59.308, avg=29.856, min=8.761, med=28.282
