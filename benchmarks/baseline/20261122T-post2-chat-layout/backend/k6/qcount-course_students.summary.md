# k6 summary

scenario: course_students

- http_req_failed: rate=0.000
- http_req_duration: avg=6.856, min=2.046, med=7.110, max=9.613, p(90)=9.269, p(95)=9.449, p(99)=9.580
- http_req_blocked: p(90)=0.024, p(95)=0.102, p(99)=0.104, avg=0.020, min=0.004, med=0.011, max=0.105
- http_req_receiving: p(95)=0.161, p(99)=0.204, avg=0.096, min=0.024, med=0.103, max=0.215, p(90)=0.154
- iterations: count=20.000, rate=4.809
- http_req_connecting: min=0.000, med=0.000, max=0.074, p(90)=0.000, p(95)=0.004, p(99)=0.060, avg=0.004
- http_req_sending: avg=0.040, min=0.016, med=0.043, max=0.053, p(90)=0.048, p(95)=0.048, p(99)=0.052
- vus: min=1.000, max=1.000
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_duration{expected_response:true}: p(95)=9.449, p(99)=9.580, avg=6.856, min=2.046, med=7.110, max=9.613, p(90)=9.269
- http_req_waiting: med=6.887, max=9.424, p(90)=9.120, p(95)=9.265, p(99)=9.392, avg=6.720, min=1.978
