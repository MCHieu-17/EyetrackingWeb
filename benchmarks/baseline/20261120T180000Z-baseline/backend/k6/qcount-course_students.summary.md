# k6 summary

scenario: course_students

- http_req_sending: max=0.072, p(90)=0.064, p(95)=0.067, p(99)=0.071, avg=0.045, min=0.029, med=0.040
- http_req_connecting: max=0.090, p(90)=0.000, p(95)=0.005, p(99)=0.073, avg=0.005, min=0.000, med=0.000
- vus: min=1.000, max=1.000
- http_req_duration: max=102.343, p(90)=99.302, p(95)=99.712, p(99)=101.817, avg=66.890, min=34.684, med=63.035
- http_req_duration{expected_response:true}: avg=66.890, min=34.684, med=63.035, max=102.343, p(90)=99.302, p(95)=99.712, p(99)=101.817
- http_req_receiving: p(90)=0.307, p(95)=0.429, p(99)=0.450, avg=0.215, min=0.100, med=0.199, max=0.455
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_waiting: avg=66.630, min=34.217, med=62.809, max=102.043, p(90)=99.074, p(95)=99.557, p(99)=101.546
- http_req_failed: rate=0.000
- http_req_blocked: avg=0.018, min=0.007, med=0.012, max=0.132, p(90)=0.014, p(95)=0.020, p(99)=0.110
- iterations: count=20.000, rate=3.731
