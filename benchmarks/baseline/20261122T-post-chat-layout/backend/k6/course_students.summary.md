# k6 summary

scenario: course_students

- http_req_sending: p(90)=0.051, p(95)=0.062, p(99)=0.118, avg=0.041, min=0.004, med=0.040, max=0.299
- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
- http_req_blocked: med=0.011, max=0.128, p(90)=0.014, p(95)=0.016, p(99)=0.095, avg=0.013, min=0.001
- http_req_receiving: p(90)=0.339, p(95)=0.422, p(99)=0.690, avg=0.132, min=0.011, med=0.068, max=0.729
- vus: min=5.000, max=5.000
- http_req_waiting: p(95)=13.000, p(99)=15.691, avg=7.620, min=1.954, med=6.909, max=16.361, p(90)=11.730
- http_req_duration: max=16.561, p(90)=12.014, p(95)=13.320, p(99)=15.816, avg=7.792, min=2.006, med=7.029
- http_req_duration{expected_response:true}: p(95)=13.320, p(99)=15.816, avg=7.792, min=2.006, med=7.029, max=16.561, p(90)=12.014
- http_req_connecting: avg=0.001, min=0.000, med=0.000, max=0.094, p(90)=0.000, p(95)=0.000, p(99)=0.065
- http_req_failed: rate=0.000
- iterations: count=241.000, rate=23.608
