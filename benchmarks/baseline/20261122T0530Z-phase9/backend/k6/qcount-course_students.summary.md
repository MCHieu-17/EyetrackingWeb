# k6 summary

scenario: course_students

- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
- http_req_duration: p(95)=12.263, p(99)=22.477, avg=9.022, min=2.688, med=9.387, max=25.030, p(90)=11.333
- http_req_waiting: p(99)=22.307, avg=8.831, min=2.623, med=9.115, max=24.885, p(90)=10.999, p(95)=11.992
- http_req_sending: p(90)=0.053, p(95)=0.058, p(99)=0.096, avg=0.043, min=0.012, med=0.042, max=0.105
- http_req_connecting: p(95)=0.004, p(99)=0.073, avg=0.004, min=0.000, med=0.000, max=0.090, p(90)=0.000
- iterations: count=20.000, rate=4.757
- vus: min=1.000, max=1.000
- http_req_receiving: p(90)=0.259, p(95)=0.264, p(99)=0.290, avg=0.148, min=0.031, med=0.157, max=0.296
- http_req_failed: rate=0.000
- http_req_duration{expected_response:true}: med=9.387, max=25.030, p(90)=11.333, p(95)=12.263, p(99)=22.477, avg=9.022, min=2.688
- http_req_blocked: avg=0.017, min=0.003, med=0.011, max=0.123, p(90)=0.014, p(95)=0.029, p(99)=0.104
