# k6 summary

scenario: teacher_courses

- http_req_sending: avg=0.044, min=0.008, med=0.042, max=0.102, p(90)=0.059, p(95)=0.074, p(99)=0.082
- http_req_failed: rate=0.000
- http_req_duration{expected_response:true}: med=8.405, max=24.994, p(90)=12.418, p(95)=13.187, p(99)=20.604, avg=9.043, min=2.710
- http_req_waiting: max=24.900, p(90)=12.265, p(95)=13.044, p(99)=20.514, avg=8.904, min=2.657, med=8.238
- vus: min=2.000, max=2.000
- http_req_blocked: med=0.011, max=0.140, p(90)=0.015, p(95)=0.026, p(99)=0.121, avg=0.015, min=0.002
- http_req_receiving: avg=0.095, min=0.010, med=0.084, max=0.376, p(90)=0.189, p(95)=0.242, p(99)=0.307
- http_req_duration: med=8.405, max=24.994, p(90)=12.418, p(95)=13.187, p(99)=20.604, avg=9.043, min=2.710
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_connecting: p(90)=0.000, p(95)=0.000, p(99)=0.093, avg=0.002, min=0.000, med=0.000, max=0.106
- iterations: rate=9.521, count=96.000
