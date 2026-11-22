# k6 summary

scenario: course_students

- http_req_blocked: min=0.004, med=0.011, max=0.119, p(90)=0.019, p(95)=0.085, p(99)=0.112, avg=0.019
- http_req_waiting: avg=7.274, min=1.933, med=7.669, max=9.316, p(90)=8.866, p(95)=9.033, p(99)=9.259
- http_req_receiving: p(99)=0.322, avg=0.135, min=0.033, med=0.120, max=0.334, p(90)=0.185, p(95)=0.275
- http_req_failed: rate=0.000
- http_req_duration: p(95)=9.261, p(99)=9.470, avg=7.451, min=1.979, med=7.872, max=9.522, p(90)=9.076
- http_req_duration{expected_response:true}: avg=7.451, min=1.979, med=7.872, max=9.522, p(90)=9.076, p(95)=9.261, p(99)=9.470
- http_req_sending: p(99)=0.063, avg=0.042, min=0.012, med=0.043, max=0.063, p(90)=0.060, p(95)=0.061
- http_req_tls_handshaking: p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000
- vus: min=1.000, max=1.000
- http_req_connecting: max=0.088, p(90)=0.000, p(95)=0.004, p(99)=0.071, avg=0.004, min=0.000, med=0.000
- iterations: count=20.000, rate=4.794
