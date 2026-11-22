# k6 summary

scenario: course_students

- http_req_duration: p(95)=100.105, p(99)=103.026, avg=70.692, min=61.338, med=65.142, max=103.757, p(90)=88.452
- vus: min=1.000, max=1.000
- http_req_duration{expected_response:true}: min=61.338, med=65.142, max=103.757, p(90)=88.452, p(95)=100.105, p(99)=103.026, avg=70.692
- http_req_waiting: p(90)=87.996, p(95)=99.886, p(99)=102.815, avg=70.448, min=61.191, med=64.991, max=103.547
- http_req_failed: rate=0.000
- http_req_blocked: avg=0.018, min=0.004, med=0.012, max=0.150, p(90)=0.012, p(95)=0.020, p(99)=0.124
- iterations: rate=3.680, count=20.000
- http_req_receiving: min=0.105, med=0.177, max=0.423, p(90)=0.290, p(95)=0.355, p(99)=0.410, avg=0.197
- http_req_connecting: avg=0.005, min=0.000, med=0.000, max=0.105, p(90)=0.000, p(95)=0.005, p(99)=0.085
- http_req_tls_handshaking: p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000
- http_req_sending: min=0.014, med=0.042, max=0.131, p(90)=0.060, p(95)=0.068, p(99)=0.118, avg=0.048
