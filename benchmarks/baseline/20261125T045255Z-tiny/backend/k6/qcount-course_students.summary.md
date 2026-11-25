# k6 summary

scenario: course_students

- http_req_tls_handshaking: p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000
- http_req_waiting: avg=7.117, min=2.229, med=7.650, max=9.249, p(90)=8.513, p(95)=8.857, p(99)=9.171
- http_req_sending: max=0.066, p(90)=0.052, p(95)=0.059, p(99)=0.064, avg=0.041, min=0.012, med=0.042
- http_req_duration{expected_response:true}: p(95)=9.014, p(99)=9.359, avg=7.296, min=2.298, med=7.872, max=9.445, p(90)=8.703
- vus: min=1.000, max=1.000
- http_req_duration: p(99)=9.359, avg=7.296, min=2.298, med=7.872, max=9.445, p(90)=8.703, p(95)=9.014
- http_req_receiving: max=0.366, p(90)=0.270, p(95)=0.334, p(99)=0.360, avg=0.137, min=0.034, med=0.121
- http_req_failed: rate=0.000
- iterations: count=20.000, rate=4.798
- http_req_blocked: max=0.103, p(90)=0.017, p(95)=0.034, p(99)=0.089, avg=0.016, min=0.003, med=0.011
- http_req_connecting: avg=0.004, min=0.000, med=0.000, max=0.076, p(90)=0.000, p(95)=0.004, p(99)=0.061
